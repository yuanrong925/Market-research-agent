"""【市场调研专属】路由函数 — 四阶段 SOP 流程的条件边路由（FactChecker 已移除）

规则4 防无限循环熔断：
- plan_retry_count 最大 2 次，超限终止并标注信息局限性
- 仅完全无匹配资料才允许重规划
- 数据冲突/内容单薄 → 标记【待人工确认】
- 全局超时 300s
"""

from langgraph.graph import END

from business.market_research.state import AgentState
from core.utils.logger import get_logger

logger = get_logger(__name__)

# 全局超时阈值（秒）
GLOBAL_TIMEOUT_SECONDS = 300

# 校验后二次检索：素材不足阈值
_VALIDATION_MIN_PASSED = 2
# 最大二次检索轮次
_MAX_VALIDATION_RETRY = 2


def route_after_planning(state: AgentState) -> str:
    """
    规划节点后的路由：
    - terminate_reason 不为空 → 模式冲突/无PDF等，直接结束，跳过数据摄入与检索
    - 有 error_message → 直接结束
    - 否则 → 进入数据摄入节点
    """
    terminate_reason = state.get("terminate_reason", "")
    if terminate_reason:
        logger.warning(f"🚫 规划阶段终止: {terminate_reason}，跳过后续节点，流程结束")
        return END

    if state.get("error_message"):
        logger.warning(f"⚠️ 规划失败: {state.get('error_message')}，终止流程")
        return END
    if state.get("circuit_breaker_triggered"):
        logger.warning(f"⚠️ 熔断触发，终止流程")
        return END

    sub_tasks = state.get("sub_tasks", [])
    logger.info(f"   📋 规划完成: {len(sub_tasks)} 个子任务将进入数据摄入阶段")
    return "data_ingestion"


def route_after_ingestion(state: AgentState) -> str:
    """
    数据摄入后的路由：
    - 有 error_message → 直接结束
    - 否则 → 进入检索节点
    """
    if state.get("error_message"):
        logger.warning(f"⚠️ 数据摄入失败: {state.get('error_message')}，终止流程")
        return END
    return "retrieval_node"


def route_after_retrieval(state: AgentState) -> str:
    """
    检索后的路由（含早停机制）：
    - early_terminate == True → 子任务检索全部不相关/文档无数据，直接截停，不进analyst+writer
    - 有 error_message → 直接结束
    - 否则 → 进入数据冲突检测节点（轻量化多源对比）

    早停准则（场景2/9）：
      - 检索节点返回 early_terminate=True 时，说明子任务级别的检索结果全部不相关
      - 此时立即截停，防止浪费 analyst+writer 的算力
      - 前端收到 early_terminate 事件后展示友好提示
    """
    if state.get("early_terminate"):
        logger.warning(f"🚫 [早停] 检索后判定全部子任务不相关，直接截停，不进analyst+writer")
        return END
    if state.get("error_message"):
        logger.warning(f"⚠️ 检索失败: {state.get('error_message')}，终止流程")
        return END
    if state.get("circuit_breaker_triggered"):
        logger.warning(f"⚠️ 熔断触发，终止流程")
        return END
    if state.get("timeout_triggered"):
        logger.warning(f"⏰ 全局超时触发，终止流程")
        return END
    return "web_ingestion"


def route_after_web_ingestion(state: AgentState) -> str:
    """
    Web 网页切片入库后的路由：
    - 有 error_message → 直接结束
    - 否则 → 进入数据冲突检测节点

    注意：
      - 即使入库失败（unified_collection 为空或降级），也不阻塞流程
      - 下游节点（chunk_validation、analyst）已做好降级容错
    """
    if state.get("error_message"):
        logger.warning(f"⚠️ Web 入库失败: {state.get('error_message')}，终止流程")
        return END
    if state.get("circuit_breaker_triggered"):
        logger.warning(f"⚠️ 熔断触发，终止流程")
        return END

    web_count = state.get("web_chunks_in_db", 0)
    logger.info(f"   🌐 Web 入库完成: {web_count} 个切片入库")
    return "data_conflict_checker"


def route_after_analyst(state: AgentState) -> str:
    """
    分析节点后的路由（规则4 防无限循环熔断）：
    - 有 error_message → 直接结束
    - timeout_triggered → 结束
    - circuit_breaker_triggered → 结束
    - 否则 → 进入 writer 节点

    重规划逻辑（当素材不足时触发）：
    - plan_retry_count >= 2 → 终止，标注信息局限性
    - 仅完全无匹配资料才允许重规划（plan_retry_count + 1）
    - 数据冲突/内容单薄 → 标记【待人工确认】，继续流程
    """
    if state.get("error_message"):
        logger.warning(f"⚠️ 分析节点失败: {state.get('error_message')}，终止流程")
        return END

    if state.get("timeout_triggered"):
        logger.warning(f"⏰ 全局超时触发，终止流程")
        return END

    if state.get("circuit_breaker_triggered"):
        logger.warning(f"⚠️ 熔断触发，终止流程")
        return END

    # 检查是否有素材
    top_k_chunks = state.get("top_k_chunks", [])
    source_materials = state.get("source_materials", [])
    has_materials = bool(top_k_chunks) or bool(source_materials)

    if not has_materials:
        # 完全无匹配资料 → 允许重规划
        plan_retry_count = state.get("plan_retry_count", 0)
        if plan_retry_count >= 2:
            # 规则4：计数器≥2时终止，标注信息局限性
            logger.warning(f"🚫 [规则4] 重规划已达上限 ({plan_retry_count})，终止流程")
            state["plan_retry_limit_reached"] = True
            state["info_limitation_note"] = "多次拓展检索仍无法获取充足资料，结论存在信息局限性，请人工补充调研"
            return END

        # 重规划
        plan_retry_count += 1
        state["plan_retry_count"] = plan_retry_count
        logger.info(f"🔄 [规则4] 无匹配资料，重规划第 {plan_retry_count} 次...")
        return "retrieval_node"  # 回到检索节点重新搜索

    # 素材极度不足（<2条有效素材）→ 直接终止，禁止下游编造
    effective_count = len([m for m in source_materials if m.get("text", "").strip()])
    if effective_count < 2:
        logger.warning(f"🚫 [规则2] 素材极度不足 ({effective_count} 条有效素材)，直接终止，禁止编造")
        state["terminate_reason"] = "INSUFFICIENT_MATERIALS"
        state["info_limitation_note"] = "有效素材不足，无法支撑报告撰写。系统已停止分析，请补充更多资料后重试"
        return END

    # 有素材但内容单薄（2~5条）→ 标记【待人工确认】，继续流程
    if effective_count < 6:
        logger.info(f"   📋 [规则2] 素材偏少 ({effective_count} 条有效素材)，标记【待人工确认】，继续流程")
        state["manual_confirm_flag"] = True

    return "writer_node"


def route_after_writer(state: AgentState) -> str:
    """
    写作节点后的路由：
    - timeout_triggered → 结束，输出部分报告
    - 否则 → 进入后置段落校验节点
    """
    if state.get("timeout_triggered"):
        logger.warning(f"⏰ 全局超时触发，输出部分报告")
        state["partial_report"] = state.get("final_report", {})
        return END
    return "post_paragraph_check"


def route_after_post_check(state: AgentState) -> str:
    """
    后置段落校验后的路由：

    路由规则（v2 按问题比例决策）：
      1. 数字问题比例 > 30% → 自动修正（只改数字），进入 paragraph_rewriter
      2. 数字问题比例 ≤ 30% → 直接输出，需人工确认，流程结束
      3. post_check_passed == True → 流程结束
      4. post_check_meltdown == True → 熔断，流程结束
      5. timeout_triggered → 超时，流程结束
      6. 无统一向量集合 → 跳过校验，流程结束

    重写限制：
      - 最多修正 1 次（只改数字，不改段落）
      - 修正后无论结果如何，都直接结束
    """
    if state.get("timeout_triggered"):
        logger.warning(f"⏰ 全局超时触发，终止流程")
        state["partial_report"] = state.get("final_report", {})
        return END

    if state.get("circuit_breaker_triggered"):
        logger.warning("⚠️ 熔断触发，终止流程")
        return END

    # 无统一向量集合 → 无素材可比对，跳过校验
    unified_collection = state.get("unified_collection", None)
    if not unified_collection:
        logger.info("   [PostCheck] 无统一向量集合，跳过后置校验，流程结束")
        return END

    post_check_passed = state.get("post_check_passed", True)
    post_check_meltdown = state.get("post_check_meltdown", False)

    if post_check_meltdown:
        logger.warning("⚠️ 后置校验熔断触发，流程结束")
        return END

    if post_check_passed:
        logger.info("✅ 后置校验全部通过，流程结束")
        return END

    # ===== 按问题比例决策 =====
    issue_ratio = state.get("post_check_issue_ratio", 0)
    rewrite_count = state.get("post_check_rewrite_count", 0)
    issue_count = state.get("post_check_issue_count", 0)
    total_numbers = state.get("post_check_total_numbers", 0)

    logger.info(f"   [Route] 数字问题比例: {issue_ratio}% ({issue_count}/{total_numbers})")

    # 已修正过一次 → 无论结果如何都结束
    if rewrite_count >= 1:
        logger.info(f"   [Route] 已修正过 {rewrite_count} 次，流程结束")
        state["info_limitation_note"] = (
            f"后置数字校验发现 {issue_count}/{total_numbers} 个数字存在问题（占比 {issue_ratio}%），"
            f"系统已尝试自动修正，请人工确认修正结果。"
        )
        return END

    if issue_ratio > 30:
        # 问题比例 > 30% → 自动修正数字（最多1次）
        logger.info(f"🔄 [Route] 问题比例 {issue_ratio}% > 30%，进入段落级数字修正")
        return "paragraph_rewriter"
    else:
        # 问题比例 ≤ 30% → 直接输出，返回用户人工选择
        logger.info(f"📋 [Route] 问题比例 {issue_ratio}% ≤ 30%，直接输出，需人工确认")
        state["manual_confirm_flag"] = True
        state["info_limitation_note"] = (
            f"后置数字校验发现 {issue_count}/{total_numbers} 个数字存在问题（占比 {issue_ratio}%），"
            f"低于自动修正阈值（30%），已原样输出，请人工逐项确认。"
        )
        return END


def route_after_validation(state: AgentState) -> str:
    """
    Chunk 校验后的路由：
    1. 通过数 < 5 且联网模式且轮次 < 2 → post_validation_retrieval（定向二次检索）
    2. 否则 → analyst_node（进入分析阶段）

    二次检索后 need_revalidation=True → 回到 chunk_validation 重新校验
    """
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    mode = "pdf_only" if manual_mode in ("disabled", "pdf_only") else "pdf_web"

    validation_stats = state.get("validation_stats", {})
    passed_count = validation_stats.get("passed", 0)
    validation_retry_count = state.get("validation_retry_count", 0)

    # 已触发二次检索后的重新校验 → 直接进入分析
    need_revalidation = state.get("need_revalidation", False)
    if need_revalidation:
        logger.info(f"   [Route] 二次检索后重新校验完成，进入分析 (passed={passed_count})")
        return "analyst_node"

    # 素材不足 + 允许联网 + 轮次未满 → 定向二次检索
    if passed_count < _VALIDATION_MIN_PASSED and mode != "pdf_only" and validation_retry_count < _MAX_VALIDATION_RETRY:
        logger.info(f"   [Route] 校验通过数 {passed_count} < {_VALIDATION_MIN_PASSED}，触发定向二次检索 (第 {validation_retry_count + 1} 轮)")
        return "post_validation_retrieval"

    # 素材充足或不允许联网或已达上限 → 直接进入分析
    logger.info(f"   [Route] 校验完成，进入分析 (passed={passed_count})")
    return "analyst_node"

