"""
第一阶段：数据摄入与清洗节点（Data Ingestion）

如果 state 中已有 cleaned_chunks 则跳过，否则从 pdf_collection 提取文本，
并尝试磁盘缓存加速。
"""

import hashlib
import json
import os
from typing import Any

from agents.state import AgentState
from tools.logger import get_logger

logger = get_logger(__name__)


# 缓存目录
_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    ".cache",
    "pdf_chunks",
)


def _compute_fingerprint(pdf_collection: Any) -> str:
    """计算 PDF 数据指纹，用于缓存键"""
    if isinstance(pdf_collection, dict):
        raw_texts = pdf_collection.get("texts", [])
        if raw_texts:
            combined = "".join(raw_texts[:5])
            return hashlib.md5(combined.encode()).hexdigest()[:16]
    return ""


def _try_load_from_cache(fingerprint: str) -> list[dict[str, Any]]:
    """尝试从磁盘缓存加载清洗后的块"""
    if not fingerprint:
        return []
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(_CACHE_DIR, f"{fingerprint}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached:
                logger.info(f"📦 [DataIngestion] 从磁盘缓存加载 {len(cached)} 个清洗块")
                return cached
        except Exception:
            pass
    return []


def _save_to_cache(fingerprint: str, chunks: list[dict[str, Any]]):
    """将清洗后的块写入磁盘缓存"""
    if not fingerprint:
        return
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(_CACHE_DIR, f"{fingerprint}.json")
    try:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, ensure_ascii=False)
        logger.info(f"   💾 已缓存到 {cache_file}")
    except Exception:
        pass


def data_ingestion_node(state: AgentState):
    """
    数据摄入与清洗节点：
      - 如果 state 中已有 cleaned_chunks 则跳过
      - 如果有 hash 匹配的磁盘缓存，直接从缓存加载
      - 否则从 pdf_collection 提取文本块
    """
    existing_chunks = state.get("cleaned_chunks")
    if existing_chunks:
        logger.info(f"📦 [DataIngestion] 已有 {len(existing_chunks)} 个清洗块，跳过")
        return {"cleaned_chunks": existing_chunks}

    pdf_collection = state.get("pdf_collection")
    if pdf_collection is None:
        logger.info("📄 [DataIngestion] 无 PDF 数据源，跳过数据摄入")
        return {"cleaned_chunks": []}

    # ---- 尝试磁盘缓存 ----
    fingerprint = _compute_fingerprint(pdf_collection)
    cached = _try_load_from_cache(fingerprint)
    if cached:
        return {"cleaned_chunks": cached}

    logger.info("🔧 [DataIngestion] 开始数据摄入与清洗...")

    # 从 pdf_collection 恢复原始文本
    all_texts = []

    if isinstance(pdf_collection, dict):
        texts = pdf_collection.get("texts", [])
        if texts:
            metadatas = pdf_collection.get("metadatas", [])
            all_texts = [
                {
                    "text": t,
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "chunk_id": f"chunk-{i}",
                }
                for i, t in enumerate(texts)
            ]

    # 如果 pdf_collection 是 chroma 形式，回退到 get() 机制
    if not all_texts:
        collection = pdf_collection.get("collection") if isinstance(pdf_collection, dict) else pdf_collection
        if collection:
            try:
                all_docs = collection.get()
                docs = all_docs.get("documents", [])
                metas = all_docs.get("metadatas", [])
                all_texts = [
                    {
                        "text": doc,
                        "metadata": metas[i] if i < len(metas) else {},
                        "chunk_id": f"chunk-{i}",
                    }
                    for i, doc in enumerate(docs)
                ]
            except Exception:
                pass

    if not all_texts:
        logger.warning("   ⚠️ 无法提取清洗数据，返回空")
        return {"cleaned_chunks": []}

    logger.info(f"   ✅ 获得 {len(all_texts)} 个清洗后的文本块")
    avg_size = sum(len(t.get("text", "")) for t in all_texts) // max(len(all_texts), 1)
    logger.info(f"   [Ingestion] 入库向量数: {len(all_texts)} 条, 平均分块大小: {avg_size} 字符")

    # 写入磁盘缓存
    _save_to_cache(fingerprint, all_texts)

    return {"cleaned_chunks": all_texts}
