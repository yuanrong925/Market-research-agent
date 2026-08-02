from typing import TypedDict, Annotated, List, Dict, Any, Optional
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    工作流的共享状态（Market Research Agent）
    """
    # ========== 用户输入 ==========
    task: str

    # ========== 消息历史 ==========
    messages: Annotated[List[str], add_messages]

    # ========== 第一阶段：数据摄入 ==========
    # 经过清洗、去噪、语义切分后的干净文本块列表
    cleaned_chunks: List[Dict[str, Any]]  # 每个元素: {"text": str, "metadata": dict, "chunk_id": str}

    # ========== 第二阶段：检索结果 ==========
    # 经过混合检索（向量+BM25）+ Rerank + Top-K 筛选后的高置信度片段
    top_k_chunks: List[Dict[str, Any]]  # 每个元素: {"text": str, "score": float, "source_index": int, "source_type": str}

    # ========== 第三阶段：Analyst 分析与规划 ==========
    # Analyst 生成的结构化大纲（含多级标题、关键论点、证据索引标注）
    analyst_outline: List[Dict[str, Any]]  # 每个元素: {"title": str, "level": int, "arguments": [str], "evidence_indices": [int]}

    # Analyst 提取的关键论点
    analyst_arguments: List[Dict[str, Any]]  # 每个元素: {"argument": str, "supporting_evidence_indices": [int], "paragraph_plan": str}

    # ========== 第四阶段：Writer 受限写作 ==========
    # 最终报告（JSON 结构化）
    final_report: str

    # 报告版本号（用于修正重试）
    report_version: int

    # ========== 第五阶段：FactChecker 验证 ==========
    # 事实核查是否通过
    fact_check_passed: bool

    # 事实核查发现的问题列表
    fact_check_issues: List[Dict[str, str]]  # 每个: {"sentence": str, "error_type": str, "impact": str, "issue": str, "suggestion": str}

    # 熔断计数器（最大重试阈值 = 3）
    retry_count: int

    # 是否已触发熔断
    circuit_breaker_triggered: bool

    # 熔断后打包的错误日志
    error_log_package: Optional[Dict[str, Any]]

    # ========== 路由与旧兼容字段 ==========
    next_step: str

    # PDF 原始数据集合（RAG 检索用）
    pdf_collection: Optional[Any]

    # 模型模式
    model_mode: str

    # 来源材料（证据锚点用）—— 保留兼容
    source_materials: List[Dict[str, Any]]

    # ========== 联网搜索标记 ==========
    # 本次任务是否使用了联网搜索
    web_search_used: bool

    # 前端手动联网搜索模式（第二层优先级）
    # "auto"  — 自动判断（由上层/下层决定）
    # "enabled"  — 强制开启联网搜索
    # "disabled" — 强制关闭联网搜索
    manual_web_search_mode: str

    # 素材池是否已冻结（冻结后下游节点只读）
    material_pool_frozen: bool

    # ========== 意图识别兜底（第一层优先级） ==========
    # 意图识别是否触发了模式覆盖
    intent_override_triggered: bool

    # 意图识别覆盖后的目标搜索模式
    intent_override_target_mode: str

    # 推送给前端的通知消息
    intent_override_notification: str

    # 引用验证结果
    citation_validation: List[Dict[str, str]]

    # 规划 & 执行进度（保留兼容）
    plan: List[Dict[str, Any]]
    current_step_index: int

    # 研究结果（保留兼容）
    research_results: List[str]
