"""【市场调研专属】路由函数 — 五阶段 SOP 流程的条件边路由

对照 workflow/routing.py 修复：
1. 删除死代码 `route_after_fact_check` 的旧版 return
2. 保留 `route_after_ingestion` 和 `route_after_fact_check`
   - 区分 `checker_node` 和 `checker_retry` 两个节点
3. 熔断检查：fact_check_passed 或 circuit_breaker_triggered → 结束

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


def route_after_planning(state: AgentState) -> str:
    """
    规划节点后的路由：
    - 有 error_message → 直接结束
    - 否则 → 进入数据摄入节点

    架构预留：后续可在此处添加子任务完整性校验、
    用户确认子任务列表等交互逻辑。
    """
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
    检索后的路由：
    - 有 error_message → 直接结束
    - 否则 → 进入数据冲突检测节点（轻量化多源对比）
    """
    if state.get("error_message"):
        logger.warning(f"⚠️ 检索失败: {state.get('error_message')}，终止流程")
        return END
    if state.get("circuit_breaker_triggered"):
        logger.warning(f"⚠️ 熔断触发，终止流程")
        return END
    if state.get("timeout_triggered"):
        logger.warning(f"⏰ 全局超时触发，终止流程")
        return END
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

    # 有素材但内容单薄/数据冲突 → 标记【待人工确认】，继续流程
    if len(source_materials) < 3:
        logger.info(f"   📋 [规则4] 素材不足 ({len(source_materials)} 条)，标记【待人工确认】，继续流程")
        state["manual_confirm_flag"] = True

    return "writer_node"


def route_after_writer(state: AgentState) -> str:
    """
    写作节点后的路由：
    - timeout_triggered → 结束，输出部分报告
    - 否则 → 进入事实核查节点
    """
    if state.get("timeout_triggered"):
        logger.warning(f"⏰ 全局超时触发，输出部分报告")
        state["partial_report"] = state.get("final_report", {})
        return END
    return "fact_checker_node"


def route_after_fact_check(state: AgentState) -> str:
    """
    事实核查后的路由（SOP 第五阶段）：
    - fact_check_passed == True → 流程结束
    - circuit_breaker_triggered == True → 熔断，流程结束
    - timeout_triggered → 超时，流程结束
    - retry_count >= 3 → 熔断，流程结束
    - analyst_outline 为空（整篇重写）→ 回到 analyst 重新规划大纲
    - 否则 → 回到 writer 重写
    """
    if state.get("fact_check_passed"):
        logger.info("✅ 事实核查通过，流程结束")
        return END

    if state.get("circuit_breaker_triggered"):
        logger.warning("⚠️ 熔断触发，终止流程")
        return END

    if state.get("timeout_triggered"):
        logger.warning("⏰ 全局超时触发，终止流程")
        return END

    retry_count = state.get("retry_count", 0)
    if retry_count >= 3:
        logger.warning(f"⚠️ 重试次数达上限 ({retry_count})，触发熔断")
        return END

    # 检查是否需要重新规划大纲
    analyst_outline = state.get("analyst_outline", [])
    if not analyst_outline:
        logger.info("🔄 需要整篇重写，重新规划大纲...")
        return "analyst_node"

    logger.info(f"🔄 需要局部重写 (retry={retry_count})，回到 writer...")
    return "writer_node"