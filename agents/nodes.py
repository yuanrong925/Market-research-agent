"""
向后兼容层 — 旧版 nodes.py 的所有导出重定向到新模块结构

当前目录结构：
  agents/           → 核心状态、配置、会话管理
  agents/providers/ → LLM、Embedding、Search 三方提供商抽象层
  agents/retrieval/ → RAG 混合检索与 Rerank 重排序模块
  agents/tools/     → 事实核查与意图识别工具
  nodes/            → 每个节点独立文件
  workflow/         → 工作流定义、路由、流转逻辑
  prompts/          → 提示词（YAML 文件）

"""

from business.market_research.nodes.ingestion import data_ingestion_node
from nodes.retrieval import retrieval_node
from nodes.analyst import analyst_node, streaming_analyst_node
from nodes.writer import writer_node, streaming_writer_node


from workflow.graph import build_workflow, build_legacy_workflow, app
from workflow.routing import (
    route_after_ingestion, route_after_retrieval, route_after_analyst,
    route_after_writer, route_after_plan,
    route_after_research, route_after_writer_deprecated,
)
from workflow.streaming import run_streaming_workflow, run_followup_streaming_workflow

planner_node = analyst_node
researcher_node = retrieval_node

