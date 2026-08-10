"""
agents/config.py — 全局配置与环境变量

从环境变量 / .env 读取所有配置，提供全局常量与 LLM 工厂函数。
所有模块通过 from agents.config import ... 获取配置。
"""

# ============================================================
#  注意：以下所有函数通过懒导入 providers/llm 避免循环依赖
#  因为 providers/llm.py 依赖本模块的配置常量
# ============================================================

import os
from typing import List


# ============================================================
#  LLM 工厂函数（re-export from providers/llm）
# ============================================================

def _import_llm():
    from agents.providers.llm import (
        get_llm as _get_llm,
        get_llm_streaming as _get_llm_streaming,
        get_llm_with_fallback as _get_llm_with_fallback,
    )
    return _get_llm, _get_llm_streaming, _get_llm_with_fallback


def get_llm(*args, **kwargs):
    getter, _, _ = _import_llm()
    return getter(*args, **kwargs)


def get_llm_streaming(*args, **kwargs):
    _, getter, _ = _import_llm()
    return getter(*args, **kwargs)


def get_llm_with_fallback(*args, **kwargs):
    _, _, getter = _import_llm()
    return getter(*args, **kwargs)


# ============================================================
#  环境变量读取
# ============================================================

# DeepSeek / 通用云端
CLOUD_API_KEY: str = os.getenv("CLOUD_API_KEY", "")
CLOUD_BASE_URL: str = os.getenv("CLOUD_BASE_URL", "https://api.deepseek.com")
CLOUD_MODEL: str = os.getenv("CLOUD_MODEL", "deepseek-chat")

# 通义千问（Qwen）
QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
QWEN_MODEL: str = os.getenv("QWEN_MODEL", "qwen-turbo")

# Ollama（本地）
OLLAMA_BASE_URL: str = "http://192.168.10.231:11434"
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen:7b")

# DashScope Embedding（通义千问向量化）
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
EMBEDDING_BASE_URL: str = os.getenv("EMBEDDING_BASE_URL", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")

# Tavily 搜索
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

# 模型模式
MODEL_MODE: str = os.getenv("MODEL_MODE", "cloud")

# 信任域名与低质域名
TRUSTED_DOMAINS: List[str] = [
    "wikipedia.org",
    "reuters.com",
    "bloomberg.com",
    "wsj.com",
    "ft.com",
    "economist.com",
    "nature.com",
    "science.org",
    "gov.cn",
    "edu.cn",
]

LOW_QUALITY_DOMAINS: List[str] = [
    "baidu.com",
    "zhuanlan.zhihu.com",
    "blog.csdn.net",
    "toutiao.com",
    "sohu.com",
    "163.com",
]

# 联网搜索开关与最大轮次
WEB_SEARCH_ENABLED: bool = os.getenv("WEB_SEARCH_ENABLED", "true").strip().lower() == "true"
MAX_SEARCH_ROUNDS: int = int(os.getenv("MAX_SEARCH_ROUNDS", "3"))


# ============================================================
#  全局搜索工具实例
# ============================================================

from agents.providers.search import search_tool  # noqa: E402

