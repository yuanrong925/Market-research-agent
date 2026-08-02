"""工具函数包 — 抽取自 nodes.py 的通用工具函数"""
from tools.llm_utils import (
    extract_llm_content,
    extract_text_content,
)
from tools.material_utils import (
    classify_trust_tier,
    check_material_sufficiency,
    build_web_query,
    grade_issues,
    count_evidence_items,
    classify_severity,
    critical_modules_ratio,
    parse_json_safe,
    targeted_rewrite,
)
from tools.logger import get_logger, get_root_logger

from tools.evidence_matcher import (
    find_evidence_anchor,
    extract_key_segments,
    extract_context,
    chunk_report,
)

__all__ = [
    # 日志
    "get_logger",
    "get_root_logger",
    # LLM 工具
    "extract_llm_content",
    "extract_text_content",
    # 素材工具
    "classify_trust_tier",
    "check_material_sufficiency",
    "build_web_query",
    "grade_issues",
    "count_evidence_items",
    "classify_severity",
    "critical_modules_ratio",
    "parse_json_safe",
    "targeted_rewrite",
    # 证据锚点
    "find_evidence_anchor",
    "extract_key_segments",
    "extract_context",
    "chunk_report",
]