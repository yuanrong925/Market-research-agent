"""Core Embedding 抽象层 — 统一嵌入接口"""

from core.embedding.provider import get_embedding, clear_embedding_cache, create_chroma_embedding_function

__all__ = ["get_embedding", "clear_embedding_cache", "create_chroma_embedding_function"]