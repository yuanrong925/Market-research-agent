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

def _create_ollama_llm(temperature: float = 0.2, streaming: bool = False, model_name: str = "") -> BaseChatModel:
    """创建本地 Ollama ChatOllama 实例"""
    from langchain_ollama import ChatOllama

    cfg = get_config()
    base_url = cfg.ollama_base_url or "http://localhost:11434"

    # 兼容用户配置了 /v1 后缀（OpenAI 兼容 API 路径，不是 Ollama 原生 API 路径）
    # ChatOllama 内部构造路径为 {base_url}/api/chat，末尾多 /v1 会导致 404
    if base_url.rstrip("/").endswith("/v1"):
        logger.warning(f"   ⚠️ 检测到 OLLAMA_BASE_URL 末尾包含 /v1，自动移除: {base_url}")
        base_url = base_url.rstrip("/").rstrip("v1").rstrip("/")

    model = model_name or cfg.ollama_model or "qwen:7b"

    logger.info(
        f"   🏠 创建 Ollama LLM: model={model}, temperature={temperature}, streaming={streaming}, base_url={base_url}"
    )
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        streaming=streaming,
        format="json",
    )


# ============================================================
#  创建 LLM 实例（不含缓存）
# ============================================================

def _create_llm(
    temperature: float = 0.2,
    model_mode: str = "cloud",
    provider: str = "deepseek",
    streaming: bool = False,
    model_name: str = "",
) -> BaseChatModel:
    """根据 model_mode 和 provider 创建 LLM 实例（无静默兜底，配置不合法直接抛出异常）"""
    model_mode = model_mode.strip().lower()
    provider = provider.strip().lower()

    if model_mode == "local":
        # local 模式下强制使用 ollama provider
        if provider != "ollama":
            logger.warning(f"   ⚠️ local 模式下 provider 应为 ollama，当前为 {provider}，已自动修正为 ollama")
            provider = "ollama"
        return _create_ollama_llm(temperature=temperature, streaming=streaming, model_name=model_name)

    if model_mode == "cloud":
        if provider == "deepseek":
            return _create_deepseek_llm(temperature=temperature, streaming=streaming)
        if provider == "qwen":
            return _create_qwen_llm(temperature=temperature, streaming=streaming)
        raise ValueError(
            f"不支持的云端 provider: '{provider}'。"
            f" 支持的 provider: 'deepseek', 'qwen'。"
            f" 请检查环境变量 LLM_PROVIDER 或调用时传入的 provider 参数。"
        )

    raise ValueError(
        f"不支持的 model_mode: '{model_mode}'。"
        f" 支持的 mode: 'cloud', 'local'。"
        f" 请检查环境变量 MODEL_MODE 或调用时传入的 model_mode 参数。"
    )


# ============================================================
#  get_llm — 非流式（带缓存复用）
# ============================================================

def get_llm(
    temperature: float = 0.2,
    model_mode: Optional[str] = None,
    provider: str = "deepseek",
    model_name: str = "",
) -> BaseChatModel:
    """获取 LLM 实例（全局缓存复用）"""
    cfg = get_config()
    model_mode = (model_mode or cfg.model_mode).strip().lower()
    provider = provider.strip().lower()

    # local 模式下强制使用 ollama provider
    if model_mode == "local" and provider != "ollama":
        logger.warning(f"[LLM] local 模式下 provider 应为 ollama，当前为 {provider}，已自动修正为 ollama")
        provider = "ollama"

    cache_key = f"{model_mode}:{provider}:{temperature}:{model_name}"
    if cache_key in _LLM_CACHE:
        logger.debug(f"[LLM] 缓存命中: {cache_key}")
        return _LLM_CACHE[cache_key]

    instance = _create_llm(
        temperature=temperature,
        model_mode=model_mode,
        provider=provider,
        streaming=False,
        model_name=model_name,
    )
    _LLM_CACHE[cache_key] = instance
    logger.info(f"[LLM] 创建新实例: mode={model_mode}, provider={provider}, temperature={temperature}, model={model_name or 'default'}")
    return instance


# ============================================================
#  get_llm_streaming — 流式（带缓存复用）
# ============================================================

def get_llm_streaming(
    temperature: float = 0.2,
    model_mode: Optional[str] = None,
    provider: str = "deepseek",
    model_name: str = "",
) -> BaseChatModel:
    """获取支持流式输出的 LLM 实例（全局缓存复用）"""
    cfg = get_config()
    model_mode = (model_mode or cfg.model_mode).strip().lower()
    provider = provider.strip().lower()

    # local 模式下强制使用 ollama provider（与 get_llm 保持完全一致）
    if model_mode == "local" and provider != "ollama":
        logger.warning(f"[LLM] local 模式下 provider 应为 ollama，当前为 {provider}，已自动修正为 ollama")
        provider = "ollama"

    cache_key = f"{model_mode}:{provider}:{temperature}:streaming:{model_name}"
    if cache_key in _LLM_STREAMING_CACHE:
        logger.debug(f"[LLM] 流式缓存命中: {cache_key}")
        return _LLM_STREAMING_CACHE[cache_key]

    instance = _create_llm(
        temperature=temperature,
        model_mode=model_mode,
        provider=provider,
        streaming=True,
        model_name=model_name,
    )
    _LLM_STREAMING_CACHE[cache_key] = instance
    logger.info(f"[LLM] 创建新流式实例: mode={model_mode}, provider={provider}, temperature={temperature}, model={model_name or 'default'}")
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
    model_name: str = "",
) -> BaseChatModel:
    """获取 LLM 实例，local 失败时自动回退到 cloud"""
    cfg = get_config()
    model_mode = (model_mode or cfg.model_mode).strip().lower()

    if model_mode == "local":
        try:
            return get_llm(temperature=temperature, model_mode="local", provider="ollama", model_name=model_name)
        except Exception as exc:
            logger.warning(f"[LLM] 本地模型失败，回退云端: {exc}")
            return get_llm(temperature=temperature, model_mode="cloud", provider=provider)

    return get_llm(temperature=temperature, model_mode=model_mode, provider=provider, model_name=model_name)