"""
LLM Provider 抽象层 — 统一 LLM 接口，支持 DeepSeek / Qwen / Ollama 切换

支持的 LLM 后端：
  - deepseek (默认云端) — DeepSeek-v4-flash 等
  - qwen (云端备选) — 通义千问 turbo/long
  - ollama (本地) — 本地部署的 ollama 模型

设计原则：
  1. 通过环境变量 MODEL_MODE 切换 cloud / local
  2. 通过 provider 参数选择具体后端
  3. 全局缓存复用 LLM 实例
  4. 支持 streaming 和普通 invoke 两种模式
"""

import os
from typing import Optional

from langchain_core.language_models.chat_models import BaseChatModel
from core.utils.logger import get_logger
from core.config import get_config

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
    from langchain_openai import ChatOpenAI

    cfg = get_config()
    api_key = cfg.cloud_api_key or os.getenv("DEEPSEEK_API_KEY", "")
    base_url = cfg.cloud_base_url or "https://api.deepseek.com"
    model = cfg.cloud_model or "deepseek-chat"

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
    from langchain_openai import ChatOpenAI

    cfg = get_config()
    api_key = cfg.qwen_api_key or os.getenv("QWEN_API_KEY", "")
    base_url = cfg.qwen_base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    model = cfg.qwen_model or "qwen-turbo"

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
    from langchain_ollama import ChatOllama

    cfg = get_config()
    base_url = cfg.ollama_base_url or "http://localhost:11434"
    model = cfg.ollama_model or "qwen:7b"

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
    """根据 model_mode 和 provider 创建 LLM 实例"""
    model_mode = model_mode.strip().lower()

    if model_mode == "local":
        return _create_ollama_llm(temperature=temperature, streaming=streaming)

    if provider == "qwen":
        return _create_qwen_llm(temperature=temperature, streaming=streaming)

    return _create_deepseek_llm(temperature=temperature, streaming=streaming)


# ============================================================
#  get_llm — 非流式（带缓存复用）
# ============================================================

def get_llm(
    temperature: float = 0.2,
    model_mode: Optional[str] = None,
    provider: str = "deepseek",
) -> BaseChatModel:
    """获取 LLM 实例（全局缓存复用）"""
    cfg = get_config()
    model_mode = (model_mode or cfg.model_mode).strip().lower()

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
    """获取支持流式输出的 LLM 实例（全局缓存复用）"""
    cfg = get_config()
    model_mode = (model_mode or cfg.model_mode).strip().lower()

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
    """获取 LLM 实例，local 失败时自动回退到 cloud"""
    cfg = get_config()
    model_mode = (model_mode or cfg.model_mode).strip().lower()

    if model_mode == "local":
        try:
            return get_llm(temperature=temperature, model_mode="local", provider="ollama")
        except Exception as exc:
            logger.warning(f"[LLM] 本地模型失败，回退云端: {exc}")
            return get_llm(temperature=temperature, model_mode="cloud", provider=provider)

    return get_llm(temperature=temperature, model_mode=model_mode, provider=provider)