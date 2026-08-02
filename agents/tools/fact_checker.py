# agents/fact_checker.py
"""
事实核查节点模块（证据锚点版本）

核心机制：「证据锚点」—— 每条论断必须在 research_materials / 原始素材
中找到原文支撑，找不到直接判 False 并丢弃，禁止 LLM 强行编造。
"""
import json
import re
from typing import Any, Dict, List, Tuple
from tools.logger import get_logger

logger = get_logger(__name__)


from langchain_core.prompts import ChatPromptTemplate

from agents.config import get_llm


def fact_check_report(
    report: str,
    research_materials: str,
    model_mode: str = "cloud",
) -> Tuple[bool, List[Dict[str, str]]]:
    """
    事实核查 + 证据锚点验证

    返回 (是否通过, 问题列表)
    问题格式：
    {
        "sentence": "有问题/无锚点的原句",
        "issue": "无来源支撑 | 与素材矛盾 | 表述夸大 | 锚点不存在",
        "suggestion": "修改建议（或 '丢弃'）",
        "evidence_anchor": "原文证据或空字符串"
    }
    """
    if not report.strip():
        return True, []

    llm = get_llm(temperature=0.1, model_mode=model_mode)

    # 分块处理（最多 3 块，每块 ≤6000 字符）
    max_chars = 6000
    max_chunks = 3
    chunks = _chunk_report(report, max_chars, max_chunks)

    all_issues = []
    for chunk in chunks:
        issues = _check_chunk_with_anchors(chunk, research_materials, llm)
        all_issues.extend(issues)

    # === 核心：证据锚点二次验证 ===
    # 对 LLM 报告的"无来源支撑"类问题，强制用文本匹配再做一次锚点查找
    filtered_issues = []
    for issue in all_issues:
        issue_type = issue.get("issue", "")
        sentence = issue.get("sentence", "")

        if "无来源支撑" in issue_type or "锚点不存在" in issue_type:
            anchor = _find_evidence_anchor(sentence, research_materials)
            if anchor:
                # 找到了锚点 → LLM 误判，跳过此问题
                continue
            else:
                # 真的没有锚点 → 标记丢弃
                issue["suggestion"] = "丢弃（无证据锚点）"
                issue["issue"] = "无来源支撑（锚点不存在）"
                filtered_issues.append(issue)
        elif "与素材矛盾" in issue_type:
            anchor = _find_evidence_anchor(sentence, research_materials)
            if not anchor:
                issue["suggestion"] = "丢弃（无法锚定矛盾证据）"
                filtered_issues.append(issue)
            else:
                issue["evidence_anchor"] = anchor
                filtered_issues.append(issue)
        else:
            # 表述夸大等轻微问题
            filtered_issues.append(issue)

    # 严重问题：只有「无来源支撑（锚点不存在）」+「与素材矛盾」才算不通过
    severe_issues = [
        i for i in filtered_issues
        if "无来源支撑" in i.get("issue", "") or "与素材矛盾" in i.get("issue", "")
    ]

    return len(severe_issues) == 0, filtered_issues


# ============================================================
#  证据锚点查找引擎（核心亮点）
# ============================================================
def _find_evidence_anchor(sentence: str, research_materials: str) -> str:
    """
    在 research_materials 中查找 sentence 的原文锚点。

    多级匹配策略：
    A. 精确子串匹配（含标点）
    B. 去标点后匹配
    C. 关键词片段分段匹配（至少2段命中）
    D. 前20字符模糊匹配
    """
    if not sentence or not research_materials:
        return ""

    clean = sentence.strip().strip('"').strip("'").strip("「」『』")
    if len(clean) < 5:
        return ""

    # 策略A：精确子串
    if clean in research_materials:
        return _extract_context(research_materials, clean)

    # 策略B：去标点匹配
    punct_pattern = re.compile(r'[，。！？、；：""\'\'（）【】\[\]{}《》\s]')
    clean_no_punct = punct_pattern.sub('', clean)
    research_no_punct = punct_pattern.sub('', research_materials)
    if len(clean_no_punct) >= 5 and clean_no_punct in research_no_punct:
        idx = research_no_punct.find(clean_no_punct)
        start = max(0, idx - 20)
        end = min(len(research_materials), idx + len(clean_no_punct) + 20)
        return research_materials[start:end]

    # 策略C：关键词片段分段匹配
    segments = _extract_key_segments(clean, min_len=5)
    matched = [s for s in segments if s in research_materials]
    if len(matched) >= 2:
        return _extract_context(research_materials, matched[0])

    # 策略D：前20字符
    short_key = clean[:20].strip()
    if len(short_key) >= 6 and short_key in research_materials:
        return _extract_context(research_materials, short_key)

    return ""


def _extract_key_segments(text: str, min_len: int = 5) -> List[str]:
    """提取文本中的有意义片段（按标点拆分）"""
    parts = re.split(r'[，。！？、；：,\.!?;:\s]+', text)
    segments = [p.strip() for p in parts if len(p.strip()) >= min_len]
    if len(segments) < 2 and len(text) > min_len * 2:
        mid = len(text) // 2
        segments = [text[:mid], text[mid:]]
    return segments


def _extract_context(text: str, keyword: str, window: int = 100) -> str:
    """在 text 中定位 keyword，返回前后 window 字符的上下文"""
    idx = text.find(keyword)
    if idx == -1:
        return keyword[:200]
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    ctx = text[start:end]
    if start > 0:
        ctx = "..." + ctx
    if end < len(text):
        ctx = ctx + "..."
    return ctx


def _chunk_report(report: str, max_chars: int, max_chunks: int) -> List[str]:
    """将报告分块"""
    chunks = []
    remaining = report
    for _ in range(max_chunks):
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
        if not remaining.strip():
            break
    if remaining.strip() and len(chunks) == max_chunks:
        logger.warning("   ⚠️ 报告过长，尾部已跳过")
    return chunks


def _check_chunk_with_anchors(
    report_chunk: str,
    research_materials: str,
    llm: Any,
) -> List[Dict[str, str]]:
    """核查报告中的一个块（含证据锚点要求）"""
    if len(report_chunk) > 7000:
        report_chunk = report_chunk[:4000] + "\n\n...(中间省略)...\n\n" + report_chunk[-3000:]

    prompt = ChatPromptTemplate.from_template(
        "你是一个严谨的事实核查员。请检查下面这段报告中的每一个事实性论断。\n\n"
        "核查规则：\n"
        "1. 每个论断必须在调研素材中有**原文支撑**（evidence anchor）\n"
        "2. 如果报告标注了引用链接 [标题](url)，检查该链接是否在调研素材中出现\n"
        "3. 数据、百分比、排名等必须有素材对应\n\n"
        "调研素材：\n{research}\n\n"
        "待核查报告内容：\n{chunk}\n\n"
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
    response = chain.invoke({"research": research_materials[:8000], "chunk": report_chunk})

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
    """
    后置校验：提取所有 [标题](url) 引用，与 source_materials 中的真实链接交叉验证
    """
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
) -> str:
    """根据事实核查结果重写报告，丢弃无锚点的条目"""
    if not issues:
        return report

    llm = get_llm(temperature=0.2, model_mode=model_mode)

    # 分离"丢弃"和"修改"项
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
    })

    return _extract_llm_content(response)
