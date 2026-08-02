"""
agents/providers — LLM、Embedding、Search 三方提供商抽象层

每个子模块提供:
  - 统一抽象接口
  - 多个后端实现（dashscope / openai / local_bge / ollama / tavily / serpapi / duckduckgo）
  - 带缓存的工厂函数 get_*, 全局复用实例
"""

from agents.providers.llm import get_llm, get_llm_streaming
from agents.providers.embedding import get_embedding, create_chroma_embedding_function, clear_embedding_cache
from agents.providers.search import get_search_provider, clear_search_cache, search_tool

__all__ = [
    # LLM
    "get_llm",
    "get_llm_streaming",
    # Embedding
    "get_embedding",
    "create_chroma_embedding_function",
    "clear_embedding_cache",
    # Search
    "get_search_provider",
    "clear_search_cache",
    "search_tool",
]