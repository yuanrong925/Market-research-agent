"""ChromaDB 客户端 — 向量数据库操作"""

import hashlib
import os
from typing import Any, Dict, List, Optional

from chromadb import Client
from chromadb.config import Settings
from core.utils.logger import get_logger

logger = get_logger(__name__)

_CHROMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "chroma_db",
)


def _file_hash(file_path: str) -> str:
    """计算文件的 MD5 哈希值，用于缓存去重"""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_chroma_client(persist_directory: Optional[str] = None) -> Client:
    """创建 ChromaDB 客户端"""
    if persist_directory:
        os.makedirs(persist_directory, exist_ok=True)
        settings = Settings(persist_directory=persist_directory, is_persistent=True)
        return Client(settings=settings)
    os.makedirs(_CHROMA_DIR, exist_ok=True)
    settings = Settings(persist_directory=_CHROMA_DIR, is_persistent=True)
    return Client(settings=settings)


class DashScopeEmbeddingFunction:
    """
    调用阿里云 DashScope（通义千问）text-embedding-v3 API 的 Chroma 兼容 embedding 函数。

    ChromaDB 支持多种调用方式（不同版本行为不同）：
      1. __call__(input: List[str])  — 批量 embedding（add 时使用）
      2. embed_query(text: str)      — 单条查询 embedding（query 时使用）
      3. embed_query(input: str)     — ChromaDB 新版本可能以 input 为关键字参数调用
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "text-embedding-v3",
        api_base: str = "",
    ):
        from core.config import get_config
        cfg = get_config()
        self.api_key = api_key or cfg.dashscope_api_key
        self.model_name = model_name
        self.api_base = api_base or cfg.embedding_base_url

    def name(self):
        return "dashscope_embedding"

    def __call__(self, input: Any) -> List[List[float]]:
        """ChromaDB 批量 embedding 接口"""
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未设置，无法使用通义千问 Embedding")
        texts = []
        if isinstance(input, list):
            for item in input:
                if isinstance(item, list):
                    texts.extend(item)
                else:
                    texts.append(item)
        else:
            texts = [input]
        return self._call_api(texts)

    def embed_query(self, *args, **kwargs) -> List[List[float]]:
        """ChromaDB 查询 embedding 接口"""
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY 未设置，无法使用通义千问 Embedding")
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
            raise RuntimeError(f"embed_query 预期返回 List[List[float]]，但内层元素是 {type(embedding)}")
        return [embedding]

    def _call_api(self, texts: List[str]) -> List[List[float]]:
        """统一调用 DashScope Embedding API"""
        import requests as req_lib
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        flat_texts = []
        for t in texts:
            if isinstance(t, list):
                for sub in t:
                    if isinstance(sub, (list, tuple)):
                        flat_texts.extend(str(x) for x in sub)
                    else:
                        flat_texts.append(str(sub))
            else:
                flat_texts.append(str(t))
        texts = flat_texts
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
            return embeddings
        except Exception as exc:
            raise RuntimeError(f"DashScope Embedding API 调用失败: {exc}")


__all__ = ["create_chroma_client", "DashScopeEmbeddingFunction"]