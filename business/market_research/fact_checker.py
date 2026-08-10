"""
【市场调研专属】事实核查模块 — v3 单次调用版

核心机制：「证据锚点」—— 每条论断必须在 research_materials / 原始素材
中找到原文支撑，找不到直接判 False 并丢弃，禁止 LLM 强行编造。

v3 变更：
  1. 移除分块逻辑（_chunk_report），改为单次 LLM 调用处理整份报告
  2. 保持证据锚点二次验证
  3. 输入截断：报告 > 8000 字时取头尾，素材 > 10000 字时取头尾
"""

import json
import re
from typing import Any, Dict, List, Tuple

from langchain_core.prompts import ChatPromptTemplate

from core.llm.provider import get_llm
from core.utils.logger import get_logger
from business.market_research.utils.constants import PDF_ONLY_CHECKER_RULE, PDF_ONLY_REWRITE_RULE

logger = get_logger(__name__)


def fact_check_report(
    report: str,
    research_materials: str,
    model_mode: str = "cloud",
    pdf_only: bool = False,
    model_name: str = "",
) -> Tuple[bool, List[Dict[str, str]]]:
    """
    事实核查 + 证据锚点验证（v3 单次 LLM 调用，不分块）

    返回 (是否通过, 问题列表)
    """
    if not report.strip():
        return True, []

    llm = get_llm(temperature=0.1, model_mode=model_mode, model_name=model_name)

    # ===== 截断超长输入避免 token 超限 =====
    truncated_report = _truncate_text(report, 8000)
    truncated_materials = _truncate_text(research_materials, 10000)

    # ===== 单次 LLM 调用检查整份报告 =====
    issues = _check_report_single_call(
        truncated_report, truncated_materials, llm, pdf_only=pdf_only
    )

    # ===== 证据锚点二次验证 =====
    filtered_issues = _validate_evidence_anchors(issues, research_materials)

    severe_issues = [
        i for i in filtered_issues
        if "无来源支撑" in i.get("issue", "") or "与素材矛盾" in i.get("issue", "")
    ]

    return len(severe_issues) == 0, filtered_issues


# ============================================================
#  证据锚点查找引擎
# ============================================================

def _find_evidence_anchor(sentence: str, research_materials: str) -> str:
    """在 research_materials 中查找 sentence 的原文锚点"""
    from business.market_research.utils.evidence_matcher import find_evidence_anchor as _find
    return _find(sentence, research_materials)


def _truncate_text(text: str, max_chars: int) -> str:
    """智能截断：保留头尾，中间用省略号替代"""
    if len(text) <= max_chars:
        return text
    head_len = max_chars * 2 // 3
    tail_len = max_chars - head_len - 50
    return text[:head_len] + f"\n\n...(中间省略，共 {len(text)} 字符)...\n\n" + text[-tail_len:]


def _check_report_single_call(
    report_text: str,
    research_materials: str,
    llm: Any,
    pdf_only: bool = False,
) -> List[Dict[str, str]]:
    """单次 LLM 调用核查整份报告，不分块"""
    pdf_only_rule = PDF_ONLY_CHECKER_RULE if pdf_only else ""

    prompt = ChatPromptTemplate.from_template(
        "你是一个严谨的事实核查员。请检查下面这份完整报告中的每一个事实性论断。\n\n"
        "核查规则：\n"
        "1. 每个论断必须在调研素材中有**原文支撑**（evidence anchor）\n"
        "2. 如果报告标注了引用链接 [标题](url)，检查该链接是否在调研素材中出现\n"
        "3. 数据、百分比、排名等必须有素材对应\n\n"
        "{pdf_only_rule}\n"
        "调研素材：\n{research}\n\n"
        "待核查完整报告：\n{chunk}\n\n"
        "请输出 JSON 格式结果（不要带 markdown 代码块标记）：\n"
        '{{\n'
        '  "issues": [\n'
        '    {{\n'
        '      "sentence": "有问题的原句（完整摘录）",\n'
        '      "issue": "无来源支撑/引用链接不存在/数据与素材矛盾/表述夸大/正确",\n'
        '      "suggestion": "修改建议或无需修改或丢弃",\n'
        '      "evidence_anchor": "调研素材中对应的原文片段（如找不到填null）"\n'
        '    }}\n'
        '  ]\n'
        '}}\n\n'
        "说明：\n"
        "- 只有明确有来源支撑的论断才标记为\"正确\"\n"
        "- 如果论断有素材支撑但标注不准确，请指出\n"
        "- 概括性总结（如\"综上所述\"类）不需要逐条核查\n"
        "- 如果所有论断都有来源支撑，issues 返回空列表\n"
        "- 仅输出 JSON，不要额外文字"
    )

    chain = prompt | llm
    response = chain.invoke({"research": research_materials, "chunk": report_text, "pdf_only_rule": pdf_only_rule})

    content = _extract_llm_content(response)
    issues = []

    try:
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
            data = json.loads(json_str)
            issues_raw = data.get("issues", [])
            for item in issues_raw:
                if isinstance(item, dict) and item.get("issue", "") != "正确":
                    issues.append(item)
    except Exception:
        pass

    return issues


def _validate_evidence_anchors(
    all_issues: List[Dict[str, str]],
    research_materials: str,
) -> List[Dict[str, str]]:
    """对 LLM 返回的问题列表进行证据锚点二次验证"""
    from business.market_research.utils.evidence_matcher import find_evidence_anchor as _find

    filtered_issues = []
    for issue in all_issues:
        issue_type = issue.get("issue", "")
        sentence = issue.get("sentence", "")

        if "无来源支撑" in issue_type or "锚点不存在" in issue_type:
            anchor = _find(sentence, research_materials)
            if anchor:
                # LLM 误判，实际有锚点 → 跳过此问题
                continue
            else:
                issue["suggestion"] = "丢弃（无证据锚点）"
                issue["issue"] = "无来源支撑（锚点不存在）"
                filtered_issues.append(issue)
        elif "与素材矛盾" in issue_type:
            anchor = _find(sentence, research_materials)
            if not anchor:
                issue["suggestion"] = "丢弃（无法锚定矛盾证据）"
                filtered_issues.append(issue)
            else:
                issue["evidence_anchor"] = anchor
                filtered_issues.append(issue)
        else:
            filtered_issues.append(issue)

    return filtered_issues


def _extract_llm_content(response: Any) -> str:
    """从 LLM 响应中提取文本内容"""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = " ".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content)
    return str(content)


def validate_citations(
    report: str,
    source_materials: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    """后置校验：提取所有 [标题](url) 引用，与 source_materials 中的真实链接交叉验证"""
    fake_citations = []
    citation_pattern = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
    citations = citation_pattern.findall(report)

    real_urls = set()
    for entry in source_materials:
        for src in entry.get("sources", []):
            url = src.get("url", "").strip().rstrip("/")
            if url:
                real_urls.add(url)

    for title, url in citations:
        url_clean = url.strip().rstrip("/")
        if url_clean and url_clean not in real_urls:
            fake_citations.append({
                "citation": f"[{title}]({url})",
                "sentence": title,
                "issue": "引用链接在搜索结果中不存在",
            })

    return fake_citations


def rewrite_with_fixes(
    report: str,
    issues: List[Dict[str, str]],
    research_materials: str,
    model_mode: str = "cloud",
    pdf_only: bool = False,
    model_name: str = "",
) -> str:
    """根据事实核查结果重写报告，丢弃无锚点的条目"""
    if not issues:
        return report

    llm = get_llm(temperature=0.2, model_mode=model_mode, model_name=model_name)

    # pdf_only 模式下追加强约束（使用全局常量）
    pdf_only_rule = PDF_ONLY_REWRITE_RULE if pdf_only else ""

    drop_sentences = []
    keep_issues = []
    for issue in issues:
        if "丢弃" in issue.get("suggestion", ""):
            drop_sentences.append(issue.get("sentence", ""))
        else:
            keep_issues.append(issue)

    issues_text_lines = []
    for i in keep_issues:
        issues_text_lines.append(
            f"- 问题句：{i.get('sentence', '')}\n"
            f"  问题：{i.get('issue', '')}\n"
            f"  建议：{i.get('suggestion', '')}"
        )
    issues_text = "\n".join(issues_text_lines)
    drop_text = "\n".join(f"- 丢弃: {s}" for s in drop_sentences) if drop_sentences else "无"

    prompt = ChatPromptTemplate.from_template(
        "你是一个专业的报告撰写人。下面是一份报告，经事实核查发现了一些问题。\n"
        "请根据调研素材和修改建议重写。\n\n"
        "{pdf_only_rule}\n"
        "原始报告：\n{report}\n\n"
        "调研素材：\n{research}\n\n"
        "需要修改的问题：\n{issues}\n\n"
        "需要删除的部分（这些论断在素材中找不到任何证据支撑，直接删除或替换为'暂无可靠数据'）：\n{drop}\n\n"
        "要求：\n"
        "1. 修改有问题的地方，删除无锚点的内容，其他保持原样\n"
        "2. 不确定的信息标注为'暂无可靠数据'\n"
        "3. 保持报告的 JSON 结构不变（如果是 JSON 格式）\n"
        "4. 直接输出修改后的完整报告"
    )

    chain = prompt | llm
    response = chain.invoke({
        "report": report,
        "research": research_materials[:8000],
        "issues": issues_text,
        "drop": drop_text,
        "pdf_only_rule": pdf_only_rule,
    })

    return _extract_llm_content(response)