"""素材工具函数 — 网页分级、充足度判断、错误分级、重写等"""

import json
import re
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

from langchain_core.prompts import ChatPromptTemplate

from core.llm.provider import get_llm
from core.config import get_config
from core.utils.logger import get_logger
from business.market_research.utils.constants import PDF_ONLY_REWRITE_RULE

logger = get_logger(__name__)


# ============================================================
#  网页信任度分级
# ============================================================

def classify_trust_tier(url: str, snippet: str = "") -> str:
    """根据 URL 域名和内容判断网页可信度等级"""
    try:
        hostname = urlparse(url).hostname or ""
    except Exception:
        hostname = ""

    cfg = get_config()

    for bad in cfg.low_quality_domains:
        if bad in hostname or bad in url:
            return "low_quality"

    for good in cfg.trusted_domains:
        if hostname.endswith(good):
            return "verified"

    return "unverified"


# ============================================================
#  素材充足度判定
# ============================================================

def check_material_sufficiency(
    top_k_chunks: List[Dict],
    task: str,
    total_source_chunks: int = 0,
) -> Dict[str, Any]:
    """检查检索结果是否充足"""
    if not top_k_chunks:
        return {"sufficient": False, "reason": "检索结果为空", "score": 0.0}

    is_small_doc = total_source_chunks > 0 and total_source_chunks <= 10

    if is_small_doc:
        min_required = 1
    elif total_source_chunks > 0 and total_source_chunks <= 15:
        min_required = 2
    else:
        min_required = 3

    if len(top_k_chunks) < min_required:
        return {
            "sufficient": False,
            "reason": f"检索结果 ({len(top_k_chunks)}) < 最少要求 ({min_required})",
            "score": 0.2,
        }

    bm25_threshold = 0.05
    vector_threshold = 0.3

    if is_small_doc:
        bm25_threshold = 0.02
        vector_threshold = 0.15

    found_relevant = False
    relevance_reasons = []
    for c in top_k_chunks:
        bm25_score = c.get("bm25_score", 0.0)
        vector_score = c.get("vector_score", 0.0)
        rerank_score = c.get("rerank_score", c.get("score", 0.0))

        if bm25_score >= bm25_threshold:
            found_relevant = True
            relevance_reasons.append(f"BM25={bm25_score:.3f}")
            break
        if vector_score >= vector_threshold:
            found_relevant = True
            relevance_reasons.append(f"vector={vector_score:.3f}")
            break
        if rerank_score >= 0.1:
            found_relevant = True
            relevance_reasons.append(f"rerank={rerank_score:.3f}")
            break

    if found_relevant:
        if len(top_k_chunks) >= 5:
            return {"sufficient": True, "reason": f"素材充足 ({'; '.join(relevance_reasons)})", "score": 0.9}
        return {"sufficient": True, "reason": f"素材基本够用 ({'; '.join(relevance_reasons)})", "score": 0.6}

    if is_small_doc:
        return {"sufficient": True, "reason": "小文档：相对排序优先，通过", "score": 0.4}
    return {"sufficient": True, "reason": "相对排序优先：top-N 内无高分，但仍有素材可用", "score": 0.3}


# ============================================================
#  联网搜索查询构建
# ============================================================

def build_web_query(task: str, round_num: int, last_round_success: bool = True) -> str:
    """构建网页搜索查询字符串"""
    if round_num >= 2 or not last_round_success:
        return task[:500]
    keywords = [w for w in task.split() if len(w) > 1]
    return " ".join(keywords[:15]) if keywords else task[:500]


# ============================================================
#  FactChecker 辅助：错误分级
# ============================================================

def grade_issues(
    issues_raw: List[Dict[str, str]],
    report: Any,
) -> List[Dict[str, str]]:
    """对 FactChecker 原始输出进行双重标注"""
    graded = []

    for issue in issues_raw:
        sentence = issue.get("sentence", "")
        issue_text = issue.get("issue", "")
        suggestion = issue.get("suggestion", "")

        if any(k in issue_text for k in ["格式", "标点", "措辞", "表述", "format"]):
            error_type = "format_error"
        elif any(k in issue_text for k in ["编造", "伪造", "虚假", "不存在", "fabricat"]):
            error_type = "evidence_fabricated"
        elif any(k in issue_text for k in ["矛盾", "冲突", "contradict", "不一致"]):
            error_type = "conclusion_contradicted"
        elif any(k in issue_text for k in ["无来源", "无证据", "缺失", "missing", "不存在"]):
            error_type = "evidence_missing"
        else:
            error_type = "evidence_missing"

        if error_type == "evidence_fabricated":
            impact = "critical"
        elif error_type == "conclusion_contradicted":
            impact = "critical"
        elif error_type == "evidence_missing" and any(
            k in sentence for k in ["核心", "关键", "主要", "最重要", "本质", "根本"]
        ):
            impact = "critical"
        elif error_type == "format_error":
            impact = "minor"
        else:
            impact = "minor"

        graded.append({
            "sentence": sentence,
            "issue": issue_text,
            "error_type": error_type,
            "impact": impact,
            "suggestion": suggestion,
        })

    return graded


def count_evidence_items(report: Any) -> int:
    """统计报告中证据项的数量"""
    if isinstance(report, dict):
        findings = report.get("关键发现", []) or report.get("key_findings", [])
        count = 0
        for finding in findings:
            evidence = finding.get("证据", []) or finding.get("evidence", [])
            count += len(evidence)
        return max(count, 1)
    return 1


def classify_severity(issues: List[Dict[str, str]], error_ratio: float) -> Tuple[str, str]:
    """根据 SOP 分级判定标准进行分类"""
    critical_issues = [i for i in issues if i.get("impact") == "critical"]
    has_critical = len(critical_issues) > 0

    if not issues:
        return "passed", "none"

    if has_critical:
        return "severe", "rewrite"

    if error_ratio > 0.5:
        return "severe", "rewrite"

    if error_ratio > 0.2:
        return "moderate", "targeted_rewrite"

    return "minor", "local_fix"


def critical_modules_ratio(issues: List[Dict[str, str]], report: Any) -> float:
    """计算受 critical 错误影响的模块占比"""
    if isinstance(report, dict):
        findings = report.get("关键发现", []) or report.get("key_findings", [])
        total_modules = len(findings) if findings else 1

        critical_sentences = set()
        for issue in issues:
            if issue.get("impact") == "critical":
                crit_sent = issue.get("sentence", "")
                critical_sentences.add(crit_sent)

        affected = 0
        for finding in findings:
            finding_text = json.dumps(finding, ensure_ascii=False)
            for crit_sent in critical_sentences:
                if crit_sent and crit_sent[:20] in finding_text:
                    affected += 1
                    break

        return affected / max(total_modules, 1)

    return 0.5


def parse_json_safe(text: str, fallback: Any) -> Any:
    """安全解析 JSON"""
    try:
        if "{" in text:
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])
    except Exception:
        pass
    return fallback


def targeted_rewrite(
    report: str,
    issues: List[Dict[str, str]],
    research_materials: str,
    model_mode: str,
    pdf_only: bool = False,
    model_name: str = "",
) -> str:
    """定向重写：仅重写有问题的模块"""
    from core.utils.llm_utils import extract_llm_content

    llm = get_llm(temperature=0.2, model_mode=model_mode, model_name=model_name)

    # pdf_only 模式下追加强约束（使用全局常量）
    pdf_only_rule = PDF_ONLY_REWRITE_RULE if pdf_only else ""

    critical_issues = [i for i in issues if i.get("impact") == "critical"]
    minor_issues = [i for i in issues if i.get("impact") == "minor"]
    drop_issues = [i for i in issues if "丢弃" in i.get("suggestion", "")]

    issues_text_lines = []
    for i in critical_issues + minor_issues:
        issues_text_lines.append(
            f"- 问题句：{i.get('sentence', '')}\n"
            f"  类型：{i.get('error_type', '')}\n"
            f"  影响：{i.get('impact', '')}\n"
            f"  建议：{i.get('suggestion', '')}"
        )
    issues_text = "\n".join(issues_text_lines)

    drop_text_lines = [f"- 丢弃: {i.get('sentence', '')}" for i in drop_issues]
    drop_text = "\n".join(drop_text_lines) if drop_text_lines else "无"

    prompt = ChatPromptTemplate.from_template(
        "你是一个专业的报告修正人。下面是一份报告，经事实核查发现了一些问题。\n"
        "请仅修改有问题的部分，保留其他内容完全不变。\n\n"
        "{pdf_only_rule}\n"
        "原始报告（JSON 格式）：\n{report}\n\n"
        "调研素材：\n{research}\n\n"
        "需要修改的问题：\n{issues}\n\n"
        "需要删除的部分：\n{drop}\n\n"
        "要求：\n"
        "1. 仅修改有问题的地方，删除无锚点的内容，其他保持完全相同\n"
        "2. 不确定的信息标注为'暂无可靠数据'\n"
        "3. 保持报告的 JSON 结构不变\n"
        "4. 直接输出修改后的完整报告（JSON 格式）"
    )

    chain = prompt | llm
    response = chain.invoke({
        "report": report,
        "research": research_materials[:8000],
        "issues": issues_text,
        "drop": drop_text,
        "pdf_only_rule": pdf_only_rule,
    })

    return extract_llm_content(response)