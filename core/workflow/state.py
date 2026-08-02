"""
Core 工作流状态定义 — 泛化状态模型

仅包含引擎运行所需的核心状态字段，不包含任何市场调研业务逻辑。
业务扩展字段在 business/market_research/state.py 中定义。
"""

from typing import Any, Dict, List, Optional, TypedDict


class AgentState(TypedDict, total=False):
    """
    核心引擎状态 — 泛化的、不拘泥于特定业务场景的状态定义。

    所有字段均为可选，不同业务场景按需填充。
    """
    # ============================================================
    #  任务与消息
    # ============================================================
    task: str                          # 任务描述
    messages: List[Dict[str, Any]]     # 消息历史（LangChain 兼容）
    next_step: str                     # 下一步节点标识

    # ============================================================
    #  检索结果
    # ============================================================
    top_k_chunks: List[Dict[str, Any]]  # 检索结果 Top-K 片段
    source_materials: List[Dict[str, Any]]  # 素材池（冻结后不可修改）
    research_results: List[str]        # 研究结果文本列表
    material_pool_frozen: bool         # 素材池是否已冻结

    # ============================================================
    #  模型配置
    # ============================================================
    model_mode: str                    # "cloud" | "local"

    # ============================================================
    #  流程控制
    # ============================================================
    current_step_index: int            # 当前步骤索引
    plan: List[Dict[str, Any]]         # 执行计划

    # ============================================================
    #  错误处理
    # ============================================================
    error_message: Optional[str]       # 错误信息
    circuit_breaker_triggered: bool    # 熔断是否触发
    error_log_package: Optional[Dict[str, Any]]  # 错误日志包

    # ============================================================
    #  网络搜索
    # ============================================================
    web_search_used: bool              # 是否使用了联网搜索

    # ============================================================
    #  Web搜索模式
    # ============================================================
    manual_web_search_mode: str        # "auto" | "enabled" | "disabled"
    intent_override_triggered: bool    # 意图识别兜底是否触发
    intent_override_target_mode: str   # 意图兜底目标模式
    intent_override_notification: str  # 意图兜底通知消息


def create_initial_state(task: str, **kwargs) -> AgentState:
    """创建初始状态"""
    state: AgentState = {
        "task": task,
        "messages": [],
        "plan": [],
        "current_step_index": 0,
        "research_results": [],
        "next_step": "",
        "model_mode": kwargs.get("model_mode", "cloud"),
        "web_search_used": False,
        "material_pool_frozen": False,
        "circuit_breaker_triggered": False,
        "top_k_chunks": [],
        "source_materials": [],
        "manual_web_search_mode": kwargs.get("manual_web_search_mode", "auto"),
        "intent_override_triggered": kwargs.get("intent_override_triggered", False),
        "intent_override_target_mode": kwargs.get("intent_override_target_mode", ""),
        "intent_override_notification": kwargs.get("intent_override_notification", ""),
    }
    state.update(kwargs)
    return state