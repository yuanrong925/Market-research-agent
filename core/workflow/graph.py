"""
Core 工作流图构建器 — 泛化的工作流图

提供通用的图构建方法，具体的节点和边由业务层注入。
"""

from typing import Any, Callable, Dict, List, Optional

from langgraph.graph import StateGraph, END
from core.utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowGraph:
    """
    泛化工作流图构建器。

    用法：
        builder = WorkflowGraph(state_schema=AgentState)
        builder.add_node("ingestion", ingestion_node)
        builder.add_node("retrieval", retrieval_node)
        builder.set_entry_point("ingestion")
        builder.add_edge("ingestion", "retrieval")
        graph = builder.compile()
    """

    def __init__(self, state_schema: type):
        self.graph = StateGraph(state_schema)
        self.node_registry: Dict[str, Callable] = {}

    def add_node(self, name: str, func: Callable) -> "WorkflowGraph":
        """添加处理节点"""
        self.graph.add_node(name, func)
        self.node_registry[name] = func
        return self

    def add_edge(self, source: str, target: str) -> "WorkflowGraph":
        """添加普通边"""
        self.graph.add_edge(source, target)
        return self

    def add_conditional_edges(
        self,
        source: str,
        router: Callable,
        path_map: Dict[str, str],
    ) -> "WorkflowGraph":
        """添加条件边"""
        self.graph.add_conditional_edges(source, router, path_map)
        return self

    def set_entry_point(self, point: str) -> "WorkflowGraph":
        """设置入口节点"""
        self.graph.set_entry_point(point)
        return self

    def set_finish_point(self, point: str) -> "WorkflowGraph":
        """设置结束节点"""
        self.graph.add_edge(point, END)
        return self

    def compile(self) -> Any:
        """编译工作流图"""
        logger.info(f"[Workflow] 编译工作流图: {len(self.node_registry)} 个节点")
        return self.graph.compile()


# ============================================================
#  便捷函数：构建标准线性工作流
# ============================================================

def build_linear_workflow(
    state_schema: type,
    nodes: List[tuple],
    entry_point: str,
) -> Any:
    """
    构建线性工作流（A → B → C → ...）

    参数:
      state_schema: 状态类型
      nodes: [(node_name, node_func), ...]
      entry_point: 入口节点名称

    返回:
      编译后的工作流图
    """
    builder = WorkflowGraph(state_schema)

    for name, func in nodes:
        builder.add_node(name, func)

    builder.set_entry_point(entry_point)

    # 连接成线性链
    node_names = [n[0] for n in nodes]
    for i in range(len(node_names) - 1):
        builder.add_edge(node_names[i], node_names[i + 1])

    # 最后一个节点连接到 END
    if node_names:
        builder.set_finish_point(node_names[-1])

    return builder.compile()