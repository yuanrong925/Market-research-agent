"""
agents — 核心模块

分层架构：
  agents/           → 核心状态、配置、会话管理
  agents/providers/ → LLM、Embedding、Search 三方提供商抽象层
  agents/retrieval/ → RAG 混合检索与 Rerank 重排序模块
  agents/tools/     → 事实核查与意图识别工具
  nodes/            → 每个节点独立文件
  workflow/         → 工作流定义、路由、流转逻辑
  prompts/          → 提示词（YAML 文件）
"""
