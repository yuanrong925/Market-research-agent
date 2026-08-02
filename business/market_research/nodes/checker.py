"""
第五阶段：验证与分级修正节点（FactChecker）

SOP 规范：
  1. 事实核查：检查每个论断是否有原文支撑
  2. 错误分级：error_type + impact（minor/critical）
  3. 分级修正：根据严重程度执行不同策略
  4. 熔断机制：最大重试3次，超限则路由至人工介入
"""

import json
from typing import Any, Dict, List

from core.llm.provider import get_llm
from core.utils.logger import get_logger

from business.market_research.state import AgentState
from business.market_research.fact_checker import fact_check_report, rewrite_with_fixes
from business.market_research.utils.constants import PDF_ONLY_RULE
from business.market_research.utils.material_utils import (
    grade_issues,
    count_evidence_items,
    classify_severity,
    critical_modules_ratio,
    parse_json_safe,
    targeted_rewrite,
)

logger = get_logger(__name__)


def fact_checker_node(state: AgentState):
    """
    验证与分级修正节点（SOP 第五阶段）
    """
    report = state.get("final_report", {})
    all_research = "\n\n".join(state.get("research_results", []))
    top_k_chunks = state.get("top_k_chunks", [])
    retry_count = state.get("retry_count", 0)
    model_mode = state.get("model_mode", "cloud")

    # ===== 检测 pdf_only 模式 =====
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    pdf_only = manual_mode in ("disabled", "pdf_only")

    # ===== 【关键加固】节点入口强制拦截 =====
    # pdf_only 模式下：保留核查逻辑，但完全禁用联网校验，仅用已有PDF素材交叉验证
    # 即使 LLM 输出中出现了网络相关资料，也以 PDF 素材为准进行核查，
    # 不引入、不依赖任何文档以外的外部信息进行校验
    if pdf_only:
        logger.info("   [FactChecker] 检测到仅 PDF 模式，强制约束：")
        logger.info(f"   {PDF_ONLY_RULE.strip()}")
        # 强制过滤：只保留 PDF 来源的素材用于核查
        pdf_only_chunks = [c for c in top_k_chunks if c.get("source_type") == "pdf"]
        if pdf_only_chunks:
            all_research = "\n\n".join([c.get("text", "") for c in pdf_only_chunks])
            logger.info(f"   [FactChecker] 仅使用 {len(pdf_only_chunks)} 条 PDF 素材进行核查")

    materials_text = all_research
    if not materials_text and top_k_chunks:
        materials_text = "\n\n".join([c.get("text", "") for c in top_k_chunks])

    # ===== 短文档快速通过：素材 < 5000 字符且已是第 2 轮以上，直接按通过处理 =====
    if len(materials_text) < 5000 and retry_count >= 1:
        logger.info(f"   [短文档快捷] 素材较短 ({len(materials_text)} 字符)，跳过后续核查轮次")
        return {
            "fact_check_passed": True,
            "fact_check_issues": [],
            "retry_count": 0,
        }

    logger.info(f"[FactChecker] 开始事实核查 (第 {retry_count + 1} 轮)...")

    # Step 1: 执行事实核查
    report_str = json.dumps(report, ensure_ascii=False) if not isinstance(report, str) else report
    passed, issues_raw = fact_check_report(report_str, materials_text, model_mode, pdf_only=pdf_only)

    # Step 2: 错误分级标注
    graded_issues = grade_issues(issues_raw, report)

    severe_count = len([i for i in graded_issues if i.get("impact") == "critical"])
    total_issues = len(graded_issues)
    total_evidence_items = count_evidence_items(report)
    error_ratio = total_issues / max(total_evidence_items, 1)

    logger.warning(f"   核查结果: {total_issues} 个问题, {severe_count} 个 critical, 错误率 {error_ratio:.1%}")

    # Step 3: 分级判定
    severity_level, action = classify_severity(graded_issues, error_ratio)
    logger.info(f"   严重等级: {severity_level}, 动作: {action}")

    if severity_level == "passed":
        logger.info("   研报通过所有核查！")
        return {
            "fact_check_passed": True,
            "fact_check_issues": [],
            "retry_count": 0,
        }

    # Step 4: 熔断检查
    if retry_count >= 3:
        logger.warning(f"   [Checker] 达到最大重试阈值（3次），触发熔断！")
        logger.error(f"   [Checker] 熔断日志: retry_count={retry_count}, issues={total_issues}, critical={severe_count}")
        error_log = {
            "task": state.get("task"),
            "retry_count": retry_count,
            "severity_level": severity_level,
            "issues": graded_issues[:20],
            "final_report": report,
            "message": "系统自动修正重试已达上限，需要人工审核介入",
        }
        return {
            "fact_check_passed": False,
            "fact_check_issues": graded_issues,
            "circuit_breaker_triggered": True,
            "error_log_package": error_log,
        }

    # Step 5: 执行修正
    if severity_level == "minor":
        logger.info("   执行局部修正...")
        rewritten_str = rewrite_with_fixes(report_str, graded_issues, materials_text, model_mode, pdf_only=pdf_only)
        rewritten_obj = parse_json_safe(rewritten_str, report)
        return {
            "fact_check_passed": False,
            "fact_check_issues": graded_issues,
            "final_report": rewritten_obj,
            "retry_count": retry_count + 1,
        }

    elif severity_level == "moderate":
        logger.info("   执行定向重写...")
        rewritten_str = targeted_rewrite(report_str, graded_issues, materials_text, model_mode, pdf_only=pdf_only)
        rewritten_obj = parse_json_safe(rewritten_str, report)
        return {
            "fact_check_passed": False,
            "fact_check_issues": graded_issues,
            "final_report": rewritten_obj,
            "retry_count": retry_count + 1,
        }

    elif severity_level == "severe":
        critical_ratio = critical_modules_ratio(graded_issues, report)
        logger.warning(f"   严重错误，critical 模块占比: {critical_ratio:.1%}")
        if critical_ratio <= 0.5:
            logger.info("   执行定向重写（<=50% 模块受影响）...")
            rewritten_str = targeted_rewrite(report_str, graded_issues, materials_text, model_mode, pdf_only=pdf_only)
            rewritten_obj = parse_json_safe(rewritten_str, report)
            return {
                "fact_check_passed": False,
                "fact_check_issues": graded_issues,
                "final_report": rewritten_obj,
                "retry_count": retry_count + 1,
            }
        else:
            logger.info("   执行整篇重写（>50% 模块受影响），重新规划大纲...")
            return {
                "fact_check_passed": False,
                "fact_check_issues": graded_issues,
                "retry_count": retry_count + 1,
                "analyst_outline": [],
                "analyst_arguments": [],
            }

    return {
        "fact_check_passed": False,
        "fact_check_issues": graded_issues,
        "retry_count": retry_count + 1,
    }