"""
【市场调研专属】五阶段 SOP 工作流图构建

SOP 流程：
  [开始] → plan_node(任务拆解) → data_ingestion → retrieval_node → analyst_node → writer_node → fact_checker_node → [结束/循环]

循环条件：
  - 事实核查通过 → 结束
  - 整篇重写 → 回到 analyst 重新规划大纲
  - 局部重写 → 回到 writer 重写
  - 重试≥3次 → 熔断结束

规则4 防无限循环熔断：
  - plan_retry_count 最大 2 次，超限终止
  - 全局超时 300s（通过 recursion_limit 和 timeout wrapper 实现）

架构预留拓展：
  - 后续可扩展 plan_node 的重规划逻辑（失败重试→动态调整子任务）
  - 子任务依赖图（DAG调度）—— 当前仅做前置一次性拆解
"""

from langgraph.graph import StateGraph, END

from core.workflow.graph import WorkflowGraph
from core.utils.logger import get_logger

from business.market_research.state import AgentState
from business.market_research.nodes import (
    plan_node,
    data_ingestion_node,
    retrieval_node,
    analyst_node,
    writer_node,
    fact_checker_node,
    data_conflict_checker_node,
)
from business.market_research.graph.routing import (
    route_after_planning,
    route_after_ingestion,
    route_after_retrieval,
    route_after_analyst,
    route_after_writer,
    route_after_fact_check,
)

logger = get_logger(__name__)

# 全局单例
_app = None


# 最大递归步数（防止无限循环）
# 正常流程：plan(1) → ingestion(1) → retrieval(1) → analyst(1) → writer(1) → checker(1) = 6 步
# 最多 2 次重规划 + 3 次重写 = 最多约 20 步
MAX_RECURSION_LIMIT = 30


def build_market_research_graph() -> StateGraph:
    """
    构建市场调研五阶段 SOP 工作流图。

    前置节点：plan_node（任务拆解）— 市场调研独有，通用问答系统不需要。
    仅新增节点，不修改任何 retrieval、原有路由逻辑。

    返回:
      StateGraph 实例（未编译）
    """
    builder = WorkflowGraph(AgentState)

    # 前置规划：任务拆解（市场调研独有）
    builder.add_node("plan_node", plan_node)

    # 第一阶段：数据摄入与清洗
    builder.add_node("data_ingestion", data_ingestion_node)

    # 第二阶段：精准检索与降噪
    builder.add_node("retrieval_node", retrieval_node)

    # 第二阶段扩展：轻量化多源数据冲突检测（检索后、分析前）
    builder.add_node("data_conflict_checker", data_conflict_checker_node)

    # 第三阶段：分析与规划
    builder.add_node("analyst_node", analyst_node)

    # 第四阶段：受限写作
    builder.add_node("writer_node", writer_node)

    # 第五阶段：验证与分级修正
    builder.add_node("fact_checker_node", fact_checker_node)

    # 设置入口：规划节点
    builder.set_entry_point("plan_node")

    # 规划 → 数据摄入（条件边：有错误直接结束）
    builder.graph.add_conditional_edges(
        "plan_node",
        route_after_planning,
        {
            "data_ingestion": "data_ingestion",
            END: END,
        },
    )

    # 数据摄入 → 检索（条件边：有错误直接结束）
    builder.graph.add_conditional_edges(
        "data_ingestion",
        route_after_ingestion,
        {
            "retrieval_node": "retrieval_node",
            END: END,
        },
    )

    # 检索 → 数据冲突检测（条件边：有错误/熔断/超时直接结束）
    builder.graph.add_conditional_edges(
        "retrieval_node",
        route_after_retrieval,
        {
            "data_conflict_checker": "data_conflict_checker",
            END: END,
        },
    )

    # 数据冲突检测 → 分析（无条件的普通边，不阻塞流程）
    builder.graph.add_edge("data_conflict_checker", "analyst_node")

    # 分析 → 写作（条件边：规则4 熔断/超时/重规划）
    builder.graph.add_conditional_edges(
        "analyst_node",
        route_after_analyst,
        {
            "writer_node": "writer_node",
            "retrieval_node": "retrieval_node",  # 规则4：无素材时重规划
            END: END,
        },
    )

    # 写作 → 核查（条件边：超时直接结束输出部分报告）
    builder.graph.add_conditional_edges(
        "writer_node",
        route_after_writer,
        {
            "fact_checker_node": "fact_checker_node",
            END: END,  # 超时直接结束
        },
    )

    # 核查 → 条件边（循环或结束）
    builder.graph.add_conditional_edges(
        "fact_checker_node",
        route_after_fact_check,
        {
            "analyst_node": "analyst_node",  # 整篇重写，重新规划大纲
            "writer_node": "writer_node",      # 局部重写
            END: END,                           # 通过或熔断
        },
    )

    return builder


def get_market_research_app():
    """
    获取市场调研工作流应用的编译实例（全局单例）。

    返回:
      编译后的 LangGraph 应用
    """
    global _app
    if _app is None:
        builder = build_market_research_graph()
        _app = builder.compile(recursion_limit=MAX_RECURSION_LIMIT)
        logger.info(f"✅ 市场调研工作流图编译完成 (recursion_limit={MAX_RECURSION_LIMIT})")
    return _app
