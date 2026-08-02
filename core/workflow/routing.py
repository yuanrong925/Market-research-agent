"""
Core 路由函数 — 泛化的条件边路由

注意：具体的路由逻辑（如熔断、核查通过等）属于业务层，
在 business/market_research/graph/routing.py 中定义。

这里只提供通用路由工具。
"""

from langgraph.graph import END
from typing import Any, Callable, Dict


# ============================================================
#  通用路由构建器
# ============================================================

def create_router(
    name: str,
    routing_func: Callable,
    path_map: Dict[str, str],
) -> Callable:
    """
    创建路由函数，适配 LangGraph 的 add_conditional_edges。

    参数:
      name: 路由名称
      routing_func: 接收 state 并返回路径键的函数
      path_map: 路径键到节点名称的映射

    返回:
      路由函数
    """
    def router(state: Any) -> str:
        route_key = routing_func(state)
        return path_map.get(route_key, END)

    router.__name__ = name
    return router