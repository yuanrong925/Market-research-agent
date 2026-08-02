"""
Embedding 抽象层 — 统一嵌入接口，屏蔽阿里云 DashScope，后续可无缝切换

支持的嵌入后端：
  - dashscope (通义千问 text-embedding-v3) — 默认云端
  - openai (text-embedding-3-small / 3-large) — 备用云端
  - local_bge (BGE-small-zh / BGE-large-zh) — 本地部署

设计原则：
  1. 所有后端实现同一个 EmbeddingInterface
  2. ChromaDB 兼容：同时支持 __call__(input) 和 embed_query()
  3. 通过环境变量 EMBEDDING_PROVIDER 切换
"""

import os
from abc import ABC, abstractmethod
from typing import Any, List, Optional
from core.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
#  抽象接口
# ============================================================

class EmbeddingInterface(ABC):
    """所有 Embedding 后端的统一抽象接口"""

    @abstractmethod
    def __call__(self, input: Any) -> List[List[float]]:
        """ChromaDB 批量 embedding 接口"""
        ...

    @abstractmethod
    def embed_query(self, *args, **kwargs) -> List[List[float]]:
        """ChromaDB 查询 embedding 接口（必须返回 List[List[float]]）"""
        ...

    @abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """标准文档嵌入接口"""
        ...


# ============================================================
#  DashScope（通义千问）实现
# ============================================================

class DashScopeEmbedding(EmbeddingInterface):
    """
    阿里云 DashScope text-embedding-v3 嵌入实现

    ChromaDB 兼容：
      - __call__(input: List[str])  — 批量 embedding（add 时使用）
      - embed_query(text: str)      — 单条查询 embedding（query 时使用）
      - embed_query(input: str)     — ChromaDB 新版本可能以 input 为关键字参数调用
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "text-embedding-v3",
        api_base: str = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
    ):
        from core.config import get_config
        cfg = get_config()

        self.api_key = api_key or cfg.dashscope_api_key
        self.model_name = model_name or cfg.embedding_model
        self.api_base = api_base or cfg.embedding_base_url

        if not self.api_key:
            raise RuntimeError(
                "DASHSCOPE_API_KEY 未设置，无法使用通义千问 Embedding。\n"
                "请设置环境变量 DASHSCOPE_API_KEY，或在 .env 文件中配置。"
            )

    def name(self) -> str:
        return f"dashscope-{self.model_name}"

    def __call__(self, input: Any) -> List[List[float]]:
        """ChromaDB 批量 embedding 接口"""
        if not isinstance(input, list):
            texts = [input]
        else:
            texts = input
        return self._call_api(texts)

    def embed_query(self, *args, **kwargs) -> List[List[float]]:
        """
        ChromaDB 查询 embedding 接口。

        兼容多种调用方式：
          - embed_query(text: str)
          - embed_query(input: str)
          - embed_query(input: List[str])

        返回: List[List[float]] — 严格对齐 ChromaDB 契约
        """
        if args:
            text = args[0]
        elif "text" in kwargs:
            text = kwargs["text"]
        elif "input" in kwargs:
            text = kwargs["input"]
        else:
            raise TypeError(f"embed_query() 收到无法识别的参数: args={args}, kwargs={kwargs}")

        if isinstance(text, list):
            text = text[0] if text else ""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        result = self._call_api([text])
        if not result or not isinstance(result, list) or not result[0]:
            raise RuntimeError(f"Embedding API 返回了异常结果: {result}")

        embedding = result[0]
        if not isinstance(embedding, list):
            raise RuntimeError(
                f"embed_query 预期返回 List[float]，但实际返回 {type(embedding)}"
            )
        return result

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """标准文档嵌入接口"""
        return self._call_api(texts)

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """统一调用 DashScope Embedding API"""
        _start = __import__("time").time()
        import requests as req_lib

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {"model": self.model_name, "input": {"texts": texts}}

        try:
            resp = req_lib.post(self.api_base, json=payload, headers=headers, timeout=120)
            if resp.status_code != 200:
                logger.warning(f"   ⚠️ Embedding API 请求失败: {resp.status_code}")
                logger.debug(f"      payload: {str(payload)[:200]}")
                logger.info(f"      response: {resp.text[:500]}")
            resp.raise_for_status()
            result = resp.json()
            embeddings = []
            for item in result.get("output", {}).get("embeddings", []):
                embeddings.append(item.get("embedding", []))
            if not embeddings:
                raise RuntimeError(f"API 返回结果中未找到 embedding 数据: {result}")
            elapsed = __import__("time").time() - _start
            logger.info(f"[Embedding] DashScope API 请求: {len(texts)} 条文本, 耗时={elapsed:.2f}s")
            return embeddings
        except Exception as exc:
            raise RuntimeError(f"DashScope Embedding API 调用失败: {exc}")


# ============================================================
#  OpenAI Embedding 实现
# ============================================================

class OpenAIEmbedding(EmbeddingInterface):
    """OpenAI text-embedding-3-small / 3-large 嵌入实现"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "text-embedding-3-small",
        api_base: Optional[str] = None,
    ):
        from openai import OpenAI as OpenAIClient

        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model_name = model_name or os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.api_base = api_base or os.getenv("OPENAI_BASE_URL", None)

        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY 未设置，无法使用 OpenAI Embedding")

        self.client = OpenAIClient(api_key=self.api_key, base_url=self.api_base)

    def name(self) -> str:
        return f"openai-{self.model_name}"

    def __call__(self, input: Any) -> List[List[float]]:
        if not isinstance(input, list):
            texts = [input]
        else:
            texts = input
        return self._call_api(texts)

    def embed_query(self, *args, **kwargs) -> List[List[float]]:
        if args:
            text = args[0]
        elif "text" in kwargs:
            text = kwargs["text"]
        elif "input" in kwargs:
            text = kwargs["input"]
        else:
            raise TypeError(f"embed_query() 收到无法识别的参数: args={args}, kwargs={kwargs}")

        if isinstance(text, list):
            text = text[0] if text else ""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        result = self._call_api([text])
        return result

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts)

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        _start = __import__("time").time()
        response = self.client.embeddings.create(input=texts, model=self.model_name)
        return [item.embedding for item in response.data]


# ============================================================
#  本地 BGE Embedding 实现
# ============================================================

class LocalBGEEmbedding(EmbeddingInterface):
    """
    本地 BGE (BAAI/bge-small-zh-v1.5) 嵌入实现

    依赖: pip install sentence-transformers
    模型会自动下载到本地缓存 (~/.cache/huggingface/hub/)
    """

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5", device: str = "cpu"):
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        logger.info(f"   🏠 加载本地 BGE 模型: {model_name} (device={device})...")
        self.model = SentenceTransformer(model_name, device=device)
        logger.info(f"   ✅ BGE 模型加载完成，向量维度: {self.model.get_sentence_embedding_dimension()}")

    def name(self) -> str:
        return f"local_bge-{self.model_name}"

    def __call__(self, input: Any) -> List[List[float]]:
        if not isinstance(input, list):
            texts = [input]
        else:
            texts = input
        return self._call_api(texts)

    def embed_query(self, *args, **kwargs) -> List[List[float]]:
        if args:
            text = args[0]
        elif "text" in kwargs:
            text = kwargs["text"]
        elif "input" in kwargs:
            text = kwargs["input"]
        else:
            raise TypeError(f"embed_query() 收到无法识别的参数: args={args}, kwargs={kwargs}")

        if isinstance(text, list):
            text = text[0] if text else ""
        if not isinstance(text, str):
            text = str(text) if text is not None else ""

        result = self._call_api([text])
        return result

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self._call_api(texts)

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        _start = __import__("time").time()
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return [emb.tolist() for emb in embeddings]


# ============================================================
#  工厂函数
# ============================================================

_EMBEDDING_CACHE: dict = {}


def get_embedding(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs,
) -> EmbeddingInterface:
    """
    获取 Embedding 实例（带缓存复用）。

    参数:
      provider: "dashscope" | "openai" | "local_bge"
      model_name: 模型名称
      api_key: API 密钥（仅 dashscope/openai 需要）
      **kwargs: 传递给具体后端的额外参数

    返回:
      EmbeddingInterface 实例
    """
    provider = provider or os.getenv("EMBEDDING_PROVIDER", "dashscope").strip().lower()

    cache_key = f"{provider}:{model_name or 'default'}"
    if cache_key in _EMBEDDING_CACHE:
        logger.debug(f"[Embedding] 缓存命中: {cache_key}")
        return _EMBEDDING_CACHE[cache_key]

    if provider == "dashscope":
        instance = DashScopeEmbedding(api_key=api_key, model_name=model_name or "text-embedding-v3")
    elif provider == "openai":
        instance = OpenAIEmbedding(api_key=api_key, model_name=model_name or "text-embedding-3-small")
    elif provider == "local_bge":
        instance = LocalBGEEmbedding(model_name=model_name or "BAAI/bge-small-zh-v1.5", **kwargs)
    else:
        raise ValueError(f"不支持的 Embedding provider: {provider}，可选: dashscope, openai, local_bge")

    _EMBEDDING_CACHE[cache_key] = instance
    logger.info(f"[Embedding] 创建新实例 provider={provider} model={model_name or model_name}")
    return instance


def clear_embedding_cache():
    """清空 Embedding 实例缓存"""
    _EMBEDDING_CACHE.clear()


def create_chroma_embedding_function(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
) -> Any:
    """
    创建 ChromaDB 兼容的 embedding function。

    返回的实例同时满足 ChromaDB 的 __call__ 和 embed_query 接口。
    """
    return get_embedding(provider=provider, model_name=model_name)