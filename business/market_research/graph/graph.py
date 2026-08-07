"""
【市场调研专属】四阶段 SOP 工作流图构建（FactChecker 已移除）

SOP 流程：
  [开始] → plan_node → data_ingestion → retrieval_node → web_ingestion
  → data_conflict_checker → chunk_validation → analyst_node → writer_node
  → post_paragraph_check → [重写循环/结束]

循环条件：
  - 后置校验通过 → 结束
  - 数字问题比例 > 30% → 自动修正（最多1次），修正后结束
  - 数字问题比例 ≤ 30% → 直接输出，需人工确认
  - 段落重写后 → 回到 post_paragraph_check 重新校验

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
    web_ingestion_node,
    analyst_node,
    writer_node,
    data_conflict_checker_node,
    chunk_validation_node,
    post_paragraph_check_node,
    paragraph_rewriter_node,
    post_validation_retrieval_node,
)
from business.market_research.graph.routing import (
    route_after_planning,
    route_after_ingestion,
    route_after_retrieval,
    route_after_analyst,
    route_after_writer,
    route_after_web_ingestion,
    route_after_post_check,
    route_after_validation,
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
    构建市场调研四阶段 SOP 工作流图。（FactChecker 已移除）

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

    # ---- 新增：Web 网页切片入库节点（检索后、冲突检测前） ----
    # 将清洗后的网页切片校验后写入统一 ChromaDB 集合（PDF + Web 混合）
    builder.add_node("web_ingestion", web_ingestion_node)

    # 第二阶段扩展：轻量化多源数据冲突检测（检索后、分析前）
    builder.add_node("data_conflict_checker", data_conflict_checker_node)

    # ---- 新增：Chunk 统一校验节点（冲突检测后、分析师前） ----
    # 对 PDF 切片 + 清洗后的网页正文做统一语义校验，失真/脱离原文的切片直接剔除
    # 通过校验的 chunk 存入 source_materials，设置 material_pool_frozen = True
    builder.add_node("chunk_validation", chunk_validation_node)

    # ---- 新增：校验后置定向二次检索（校验通过数 < 5 时触发） ----
    # 分析缺失的子主题方向，执行定向联网搜索，最多 2 轮
    builder.add_node("post_validation_retrieval", post_validation_retrieval_node)

    # 第三阶段：分析与规划
    builder.add_node("analyst_node", analyst_node)

    # 第四阶段：受限写作
    builder.add_node("writer_node", writer_node)

    # ---- 新增：后置段落校验节点（写作后、事实核查前） ----
    # 按段落切分报告 → LLM 提取主题断言 → 向量召回比对 → 分级判定 → 路由
    builder.add_node("post_paragraph_check", post_paragraph_check_node)

    # ---- 新增：段落级局部改写节点（后置校验发现问题后执行） ----
    # 只改写有问题的段落，不重新生成整篇报告
    builder.add_node("paragraph_rewriter", paragraph_rewriter_node)

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

    # 检索 → Web 网页切片入库（条件边：有错误/熔断/超时直接结束）
    builder.graph.add_conditional_edges(
        "retrieval_node",
        route_after_retrieval,
        {
            "web_ingestion": "web_ingestion",
            END: END,
        },
    )

    # Web 入库 → 数据冲突检测（条件边：有错误直接结束）
    builder.graph.add_conditional_edges(
        "web_ingestion",
        route_after_web_ingestion,
        {
            "data_conflict_checker": "data_conflict_checker",
            END: END,
        },
    )

    # 数据冲突检测 → Chunk 统一校验（无条件的普通边，不阻塞流程）
    builder.graph.add_edge("data_conflict_checker", "chunk_validation")

    # Chunk 校验 → 条件边（校验通过数 < 5 → 定向二次检索；否则 → 分析）
    builder.graph.add_conditional_edges(
        "chunk_validation",
        route_after_validation,
        {
            "post_validation_retrieval": "post_validation_retrieval",
            "analyst_node": "analyst_node",
        },
    )

    # 定向二次检索 → 再次 Chunk 校验（重新校验合并后的素材）
    builder.graph.add_edge("post_validation_retrieval", "chunk_validation")

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

    # 写作 → 后置段落校验（条件边：超时直接结束输出部分报告）
    builder.graph.add_conditional_edges(
        "writer_node",
        route_after_writer,
        {
            "post_paragraph_check": "post_paragraph_check",
            END: END,  # 超时直接结束
        },
    )

    # 后置段落校验 → 条件边（结束/重写循环/熔断）
    builder.graph.add_conditional_edges(
        "post_paragraph_check",
        route_after_post_check,
        {
            "paragraph_rewriter": "paragraph_rewriter",  # 需要重写（medium/major），进入段落级改写
            END: END,                                  # 通过/熔断/问题比例≤30%，直接结束
        },
    )

    # 段落级改写完成后 → 再次进入后置校验（循环验证）
    builder.graph.add_edge("paragraph_rewriter", "post_paragraph_check")

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
