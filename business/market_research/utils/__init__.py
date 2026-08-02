"""【市场调研专属】业务工具函数"""

from business.market_research.utils.material_utils import (
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
from business.market_research.utils.evidence_matcher import (
    find_evidence_anchor,
    extract_key_segments,
    extract_context,
    chunk_report,
)
from business.market_research.utils.intent_detector import (
    detect_document_summary_intent,
    get_override_mode_from_intent,
)

__all__ = [
    "classify_trust_tier",
    "check_material_sufficiency",
    "build_web_query",
    "grade_issues",
    "count_evidence_items",
    "classify_severity",
    "critical_modules_ratio",
    "parse_json_safe",
    "targeted_rewrite",
    "find_evidence_anchor",
    "extract_key_segments",
    "extract_context",
    "chunk_report",
    "detect_document_summary_intent",
    "get_override_mode_from_intent",
]