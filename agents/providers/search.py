"""
Search 工具抽象层 — 统一搜索接口，屏蔽 Tavily，方便替换 SerpAPI 等

支持的搜索后端：
  - tavily (默认) — TavilySearchResults
  - serpapi — Google Search via SerpAPI
  - duckduckgo — DuckDuckGo (免费，无需 API Key)

设计原则：
  1. 所有后端实现同一个 SearchInterface
  2. 通过环境变量 SEARCH_PROVIDER 切换后端
  3. 全局复用搜索实例
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from tools.logger import get_logger

logger = get_logger(__name__)



# ============================================================
#  抽象接口
# ============================================================

class SearchInterface(ABC):
    """所有搜索后端的统一抽象接口"""

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        _start = __import__("time").time()
        """
        执行搜索，返回统一格式的结果列表。

        返回格式:
        [
            {
                "title": str,
                "url": str,
                "content": str,  # 页面摘要/片段
                "snippet": str,  # 简短摘要（兼容旧版）
                "source": str,   # 搜索来源标识
            },
            ...
        ]
        """
        ...

    def invoke(self, query: str, **kwargs) -> Any:
        """兼容 LangChain Tool 的 invoke 接口"""
        results = self.search(query, max_results=kwargs.get("max_results", 5))
        return {"results": results}


# ============================================================
#  Tavily 实现
# ============================================================

class TavilySearch(SearchInterface):
    """Tavily 搜索实现"""

    def __init__(self, api_key: Optional[str] = None, max_results: int = 5):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY", "")
        self.max_results = max_results

        if not self.api_key:
            logger.warning("   ⚠️ TAVILY_API_KEY 未设置，Tavily 搜索不可用")
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        _start = __import__("time").time()
        """执行 Tavily 搜索"""
        if not self.api_key:
            return []

        try:
            from langchain_tavily import TavilySearch as TavilyTool

            tool = TavilyTool(max_results=max_results)
            response = tool.invoke(query)
        except ImportError:
            try:
                from langchain_community.tools.tavily_search import TavilySearchResults

                tool = TavilySearchResults(max_results=max_results)
                response = tool.invoke(query)
            except ImportError:
                logger.warning("   ⚠️ 未安装 Tavily 包，请执行: pip install langchain-tavily 或 langchain-community")
                return []

        elapsed = __import__("time").time() - _start
        logger.info(f"[Search] Tavily 搜索: {query[:40]}... max_results={max_results}, 耗时={elapsed:.2f}s")
        return self._parse_response(response)

    def _parse_response(self, response: Any) -> List[Dict[str, Any]]:
        """将 Tavily 原始响应解析为统一格式"""
        results = []

        if isinstance(response, dict):
            items = response.get("results", [])
        elif isinstance(response, list):
            items = response
        else:
            items = [{"content": str(response), "url": ""}]

        for item in items:
            if isinstance(item, dict):
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", item.get("snippet", ""))
                snippet = item.get("snippet", content[:200])
            else:
                title = ""
                url = ""
                content = str(item)
                snippet = str(item)[:200]

            results.append({
                "title": title,
                "url": url,
                "content": content,
                "snippet": snippet,
                "source": "tavily",
            })

        return results


# ============================================================
#  SerpAPI 实现
# ============================================================

class SerpAPISearch(SearchInterface):
    """SerpAPI Google 搜索实现"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("SERPAPI_API_KEY", "")

        if not self.api_key:
            logger.warning("   ⚠️ SERPAPI_API_KEY 未设置，SerpAPI 搜索不可用")
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        _start = __import__("time").time()
        if not self.api_key:
            return []

        try:
            import requests

            params = {
                "q": query,
                "api_key": self.api_key,
                "num": max_results,
                "engine": "google",
            }
            resp = requests.get("https://serpapi.com/search", params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get("organic_results", [])[:max_results]:
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "content": item.get("snippet", ""),
                    "snippet": item.get("snippet", ""),
                    "source": "serpapi",
                })
            return results

        except ImportError:
            logger.warning("   ⚠️ 请安装 requests 库: pip install requests")
            return []
        except Exception as e:
            logger.warning(f"   ⚠️ SerpAPI 搜索失败: {e}")
            return []


# ============================================================
#  DuckDuckGo 实现（免费，无需 API Key）
# ============================================================

class DuckDuckGoSearch(SearchInterface):
    """DuckDuckGo 搜索实现（免费，无需 API Key）"""

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        _start = __import__("time").time()
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = []
                for i, r in enumerate(ddgs.text(query, max_results=max_results)):
                    if i >= max_results:
                        break
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "content": r.get("body", ""),
                        "snippet": r.get("body", "")[:200],
                        "source": "duckduckgo",
                    })
                return results

        except ImportError:
            logger.warning("   ⚠️ 请安装 duckduckgo_search 库: pip install duckduckgo-search")
            return []
        except Exception as e:
            logger.warning(f"   ⚠️ DuckDuckGo 搜索失败: {e}")
            return []


# ============================================================
#  工厂函数
# ============================================================

_SEARCH_CACHE: dict = {}


def get_search_provider(provider: Optional[str] = None, **kwargs) -> SearchInterface:
    """
    获取搜索实例（带缓存复用）。

    参数:
      provider: "tavily" | "serpapi" | "duckduckgo"，
               不指定则从环境变量 SEARCH_PROVIDER 读取（默认 tavily）
      **kwargs: 传递给具体后端的额外参数（如 api_key, max_results）

    返回:
      SearchInterface 实例
    """
    provider = provider or os.getenv("SEARCH_PROVIDER", "tavily").strip().lower()

    cache_key = f"search:{provider}"
    if cache_key in _SEARCH_CACHE:
        logger.debug(f"[Search] 缓存命中: {cache_key}")
        return _SEARCH_CACHE[cache_key]

    if provider == "tavily":
        instance = TavilySearch(**kwargs)
    elif provider == "serpapi":
        instance = SerpAPISearch(**kwargs)
    elif provider == "duckduckgo":
        instance = DuckDuckGoSearch(**kwargs)
    else:
        raise ValueError(f"不支持的搜索 provider: {provider}，可选: tavily, serpapi, duckduckgo")

    _SEARCH_CACHE[cache_key] = instance
    logger.info(f"[Search] 创建新实例 provider={provider}")
    return instance


def clear_search_cache():
    """清空搜索实例缓存"""
    _SEARCH_CACHE.clear()


# ============================================================
#  兼容旧接口：全局搜索实例
# ============================================================

# 旧版 config.py 中全局搜索实例的替代
# 用法: from agents.search_provider import search_tool
search_tool = get_search_provider()
