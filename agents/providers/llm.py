"""
agents/providers/llm.py — LLM 实例工厂（统一接口，支持 DeepSeek / Qwen / Ollama）

设计原则：
  1. 通过环境变量 MODEL_MODE 切换 cloud / local
  2. 通过 provider 参数选择具体后端
  3. 全局缓存复用 LLM 实例
  4. 支持 streaming 和普通 invoke 两种模式
"""

import os
from typing import Any, Dict, List, Optional

from agents.config import (
    CLOUD_API_KEY,
    CLOUD_BASE_URL,
    DASHSCOPE_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    MODEL_MODE,
    OLLAMA_BASE_URL,
)

from langchain_core.language_models.chat_models import BaseChatModel
from tools.logger import get_logger

logger = get_logger(__name__)

# ============================================================
#  LLM 缓存（全局复用）
# ============================================================

_LLM_CACHE: dict = {}
_LLM_STREAMING_CACHE: dict = {}

# ============================================================
#  DeepSeek 实现（云端，默认）
# ============================================================

def _create_deepseek_llm(temperature: float = 0.2, streaming: bool = False) -> BaseChatModel:
    """创建 DeepSeek ChatOpenAI 实例"""
    from agents.config import CLOUD_API_KEY, CLOUD_BASE_URL, CLOUD_MODEL
    from langchain_openai import ChatOpenAI

    api_key = CLOUD_API_KEY or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = CLOUD_BASE_URL or "https://api.deepseek.com"
    model = CLOUD_MODEL or "deepseek-chat"

    if not api_key:
        logger.warning("   ⚠️ CLOUD_API_KEY 未设置，DeepSeek 将使用空密钥尝试")

    logger.info(
        f"   🚀 创建 DeepSeek LLM: model={model}, temperature={temperature}, streaming={streaming}"
    )
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
        streaming=streaming,
    )


# ============================================================
#  Qwen（通义千问）实现（云端备选）
# ============================================================

def _create_qwen_llm(temperature: float = 0.2, streaming: bool = False) -> BaseChatModel:
    """创建通义千问 ChatOpenAI 实例（兼容 OpenAI SDK）"""
    from agents.config import QWEN_API_KEY, QWEN_BASE_URL, QWEN_MODEL
    from langchain_openai import ChatOpenAI

    api_key = QWEN_API_KEY or os.getenv("QWEN_API_KEY", "")
    base_url = QWEN_BASE_URL or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = QWEN_MODEL or "qwen-turbo"

    if not api_key:
        logger.warning("   ⚠️ QWEN_API_KEY 未设置，通义千问将使用空密钥尝试")

    logger.info(
        f"   🚀 创建 Qwen LLM: model={model}, temperature={temperature}, streaming={streaming}"
    )
    return ChatOpenAI(
        model=model,
        temperature=temperature,
        api_key=api_key,
        base_url=base_url,
        streaming=streaming,
    )


# ============================================================
#  Ollama 实现（本地）
# ============================================================

def _create_ollama_llm(temperature: float = 0.2, streaming: bool = False) -> BaseChatModel:
    """创建本地 Ollama ChatOllama 实例"""
    from agents.config import OLLAMA_BASE_URL, OLLAMA_MODEL
    from langchain_ollama import ChatOllama

    base_url = OLLAMA_BASE_URL or "http://localhost:11434"
    model = OLLAMA_MODEL or "qwen:7b"

    logger.info(
        f"   🏠 创建 Ollama LLM: model={model}, temperature={temperature}, streaming={streaming}, base_url={base_url}"
    )
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        streaming=streaming,
    )


# ============================================================
#  创建 LLM 实例（不含缓存）
# ============================================================

def _create_llm(
    temperature: float = 0.2,
    model_mode: str = "cloud",
    provider: str = "deepseek",
    streaming: bool = False,
) -> BaseChatModel:
    """
    根据 model_mode 和 provider 创建 LLM 实例。

    参数:
      temperature: 温度参数
      model_mode: "cloud" | "local"
      provider: "deepseek" | "qwen" | "ollama"
      streaming: 是否启用流式输出

    返回:
      BaseChatModel 实例（ChatOpenAI 或 ChatOllama）
    """
    model_mode = model_mode.strip().lower()

    # local 模式始终使用 Ollama
    if model_mode == "local":
        return _create_ollama_llm(temperature=temperature, streaming=streaming)

    # cloud 模式根据 provider 选择
    if provider == "qwen":
        return _create_qwen_llm(temperature=temperature, streaming=streaming)

    # 默认：deepseek
    return _create_deepseek_llm(temperature=temperature, streaming=streaming)


# ============================================================
#  get_llm — 非流式（带缓存复用）
# ============================================================

def get_llm(
    temperature: float = 0.2,
    model_mode: Optional[str] = None,
    provider: str = "deepseek",
) -> BaseChatModel:
    """
    获取 LLM 实例（全局缓存复用）。

    参数:
      temperature: 温度参数
      model_mode: "cloud" | "local"，不指定则从环境变量 MODEL_MODE 读取
      provider: "deepseek" | "qwen" | "ollama"

    返回:
      ChatOpenAI 或 ChatOllama 实例
    """
    model_mode = (model_mode or MODEL_MODE).strip().lower()

    # 构造缓存键
    cache_key = f"{model_mode}:{provider}:{temperature}"
    if cache_key in _LLM_CACHE:
        logger.debug(f"[LLM] 缓存命中: {cache_key}")
        return _LLM_CACHE[cache_key]

    instance = _create_llm(
        temperature=temperature,
        model_mode=model_mode,
        provider=provider,
        streaming=False,
    )
    _LLM_CACHE[cache_key] = instance
    logger.info(f"[LLM] 创建新实例: mode={model_mode}, provider={provider}, temperature={temperature}")
    return instance


# ============================================================
#  get_llm_streaming — 流式（带缓存复用）
# ============================================================

def get_llm_streaming(
    temperature: float = 0.2,
    model_mode: Optional[str] = None,
    provider: str = "deepseek",
) -> BaseChatModel:
    """
    获取支持流式输出的 LLM 实例（全局缓存复用）。

    参数:
      temperature: 温度参数
      model_mode: "cloud" | "local"，不指定则从环境变量 MODEL_MODE 读取
      provider: "deepseek" | "qwen" | "ollama"

    返回:
      ChatOpenAI 或 ChatOllama 实例（streaming=True）
    """
    model_mode = (model_mode or MODEL_MODE).strip().lower()

    # 构造缓存键
    cache_key = f"{model_mode}:{provider}:{temperature}:streaming"
    if cache_key in _LLM_STREAMING_CACHE:
        logger.debug(f"[LLM] 流式缓存命中: {cache_key}")
        return _LLM_STREAMING_CACHE[cache_key]

    instance = _create_llm(
        temperature=temperature,
        model_mode=model_mode,
        provider=provider,
        streaming=True,
    )
    _LLM_STREAMING_CACHE[cache_key] = instance
    logger.info(f"[LLM] 创建新流式实例: mode={model_mode}, provider={provider}, temperature={temperature}")
    return instance


# ============================================================
#  缓存管理
# ============================================================

def clear_llm_cache():
    """清空所有 LLM 缓存"""
    _LLM_CACHE.clear()
    _LLM_STREAMING_CACHE.clear()
    logger.info("[LLM] 缓存已清空")


# ============================================================
#  兼容旧接口：fallback 处理
# ============================================================

def get_llm_with_fallback(
    temperature: float = 0.2,
    model_mode: Optional[str] = None,
    provider: str = "deepseek",
) -> BaseChatModel:
    """
    获取 LLM 实例，local 失败时自动回退到 cloud。

    参数:
      temperature: 温度参数
      model_mode: "cloud" | "local"
      provider: "deepseek" | "qwen" | "ollama"

    返回:
      BaseChatModel 实例
    """
    model_mode = (model_mode or MODEL_MODE).strip().lower()

    # 优先尝试 local
    if model_mode == "local":
        try:
            return get_llm(temperature=temperature, model_mode="local", provider="ollama")
        except Exception as exc:
            logger.warning(f"[LLM] 本地模型失败，回退云端: {exc}")
            return get_llm(temperature=temperature, model_mode="cloud", provider=provider)

    return get_llm(temperature=temperature, model_mode=model_mode, provider=provider)


