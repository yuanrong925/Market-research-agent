"""工作流图定义 — 构建 SOP 五阶段闭环工作流"""

from langgraph.graph import END, START, StateGraph

from agents.state import AgentState
from nodes import (
    data_ingestion_node,
    retrieval_node,
    analyst_node,
    writer_node,
    fact_checker_node,
)
from workflow.routing import (
    route_after_ingestion,
    route_after_retrieval,
    route_after_analyst,
    route_after_writer,
    route_after_fact_check,
)


def build_workflow(model_mode=None):
    """
    构建 SOP 五阶段闭环工作流

    流转路径：
      原始素材 → 数据摄入与清洗 → 精准检索与降噪 → Analyst(规划)
      → Writer(写作) → FactChecker(验证) → 合格输出 / 熔断人工介入
    """
    builder = StateGraph(AgentState)

    # 添加所有节点
    builder.add_node("data_ingestion", data_ingestion_node)
    builder.add_node("retrieval", retrieval_node)
    builder.add_node("analyst", analyst_node)
    builder.add_node("writer", writer_node)
    builder.add_node("fact_checker", fact_checker_node)

    # 设置流转
    builder.add_edge(START, "data_ingestion")
    builder.add_conditional_edges("data_ingestion", route_after_ingestion)
    builder.add_conditional_edges("retrieval", route_after_retrieval)
    builder.add_conditional_edges("analyst", route_after_analyst)
    builder.add_conditional_edges("writer", route_after_writer)
    builder.add_conditional_edges("fact_checker", route_after_fact_check)

    return builder.compile()


def build_legacy_workflow():
    """旧版 3 节点工作流（plan → research → write）"""
    from workflow.routing import (
        route_after_plan,
        route_after_research,
        route_after_writer_deprecated,
        route_after_fact_check_deprecated,
    )

    builder = StateGraph(AgentState)
    builder.add_node("planner", analyst_node)
    builder.add_node("researcher", retrieval_node)
    builder.add_node("writer", writer_node)
    builder.add_node("fact_checker", fact_checker_node)

    builder.add_edge(START, "planner")
    builder.add_conditional_edges("planner", route_after_plan)
    builder.add_conditional_edges("researcher", route_after_research)
    builder.add_conditional_edges("writer", route_after_writer_deprecated)
    builder.add_conditional_edges("fact_checker", route_after_fact_check_deprecated)

    return builder.compile()


# 默认导出新工作流
app = build_workflow()
