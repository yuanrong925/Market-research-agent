"""Core Search 抽象层 — 统一搜索接口"""

from core.search.provider import get_search_provider, clear_search_cache, SearchInterface

__all__ = ["get_search_provider", "clear_search_cache", "SearchInterface"]