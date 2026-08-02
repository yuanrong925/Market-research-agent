"""路由函数 — 工作流节点间的条件边"""

from langgraph.graph import END
from tools.logger import get_logger

logger = get_logger(__name__)


from agents.state import AgentState


def route_after_ingestion(state: AgentState):
    """数据摄入完成后 → 检索"""
    return "retrieval"


def route_after_retrieval(state: AgentState):
    """检索完成后 → Analyst（规划）"""
    return "analyst"


def route_after_analyst(state: AgentState):
    """Analyst 规划完成后 → Writer（写作）"""
    return "writer"


def route_after_writer(state: AgentState):
    """写作完成后 → FactChecker（核查）"""
    return "fact_checker"


def route_after_fact_check(state: AgentState):
    """核查完成后：决定是继续修正、重新规划还是结束"""
    if state.get("circuit_breaker_triggered", False):
        logger.warning("🔴 [路由] 熔断已触发 → 结束流转，等待人工介入")
    logger.warning("   [Workflow] 路由决策: circuit_breaker → END")
    return END

    if state.get("fact_check_passed", True):
        logger.info("✅ [路由] 核查通过 → 研报输出")
    logger.info("   [Workflow] 路由决策: check_passed → OUTPUT")
    return END

    retry_count = state.get("retry_count", 0)
    issues = state.get("fact_check_issues", [])

    if retry_count >= 3:
        logger.warning(f"🔴 [路由] 重试 {retry_count} 次已达上限 → 熔断")
    logger.warning(f"   [Workflow] 路由决策: retry_limit_exceeded → CIRCUIT_BREAKER")
    return END

    if not issues:
        logger.warning("⚠️ [路由] 无具体问题但未通过核查 → 直接结束")
        return END

    outline = state.get("analyst_outline", [])
    if not outline:
        logger.info("🔄 [路由] 大纲已清空 → 返回 Analyst 重新规划")
    logger.info("   [Workflow] 路由决策: outline_cleared → ANALYST")
    return "analyst"

    logger.info("🔄 [路由] 返回 Writer 继续修正")
    logger.info("   [Workflow] 路由决策: needs_correction → WRITER")
    return "writer"


# ============================================================
#  旧版路由函数兼容
# ============================================================

def route_after_plan(state: AgentState):
    return "researcher"


def route_after_research(state: AgentState):
    if state["current_step_index"] < len(state.get("plan", [])):
        return "researcher"
    return "writer"


def route_after_writer_deprecated(state: AgentState):
    return "fact_checker"


def route_after_fact_check_deprecated(state: AgentState):
    if state.get("fact_check_passed", True):
        return END
    return "writer"
