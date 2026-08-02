"""
第一阶段：数据摄入与清洗节点（Ingestion）

SOP 规范：
  1. 支持 PDF 文件解析（PyMuPDF/fitz）
  2. 文本清洗（去噪、去重、分段）
  3. 构建向量索引（ChromaDB）
"""

import re
from typing import Any

from core.utils.logger import get_logger
from business.market_research.state import AgentState

logger = get_logger(__name__)


# ============================================================
#  PDF 解析
# ============================================================

def _extract_text_from_pdf(file_path: str) -> str:
    """使用 PyMuPDF 提取 PDF 文本"""
    import fitz
    doc = fitz.open(file_path)
    texts = []
    for page in doc:
        texts.append(page.get_text())
    doc.close()
    return "\n".join(texts)


# ============================================================
#  文本清洗
# ============================================================

def _clean_text(text: str) -> str:
    """清洗文本：去除多余空白、特殊字符"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', text)
    return text.strip()


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict[str, Any]]:
    """将文本分块"""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            end = text.rfind('\n', start, end)
            if end == -1 or end <= start:
                end = min(start + chunk_size, len(text))
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "source_index": len(chunks),
                "source_type": "pdf",
            })
        start = end - overlap if end < len(text) else len(text)
    return chunks


def _build_pdf_collection(texts: list[str], metadatas: list[dict], model_mode: str) -> Any:
    """构建 PDF 向量集合"""
    from core.retrieval.chroma import create_chroma_client, DashScopeEmbeddingFunction
    from core.retrieval.hybrid import HybridRetriever
    from core.config import get_config

    cfg = get_config()

    try:
        client = create_chroma_client()
        embedding_fn = DashScopeEmbeddingFunction(
            api_key=cfg.dashscope_api_key,
            model_name=cfg.embedding_model,
            api_base=cfg.embedding_base_url,
        )

        collection = client.get_or_create_collection(
            name=f"pdf-{len(texts)}-{hash(''.join(texts)) % 10000}",
            embedding_function=embedding_fn,
        )

        if collection.count() == 0:
            collection.add(
                ids=[f"doc-{i}" for i in range(len(texts))],
                documents=texts,
                metadatas=metadatas,
            )

        hybrid = HybridRetriever(chroma_collection=collection)
        hybrid.build_index(texts, metadatas, chroma_collection=collection)

        return {"type": "chroma", "collection": collection, "hybrid": hybrid}
    except Exception as exc:
        logger.warning(f"Chroma 构建失败，降级到内存模式: {exc}")
        hybrid = HybridRetriever()
        hybrid.build_index(texts, metadatas)
        return {"type": "inmemory", "texts": texts, "metadatas": metadatas, "fallback": True, "hybrid": hybrid}


def data_ingestion_node(state: AgentState):
    """数据摄入节点（SOP 第一阶段）"""
    task = state.get("task", "")
    pdf_collection = state.get("pdf_collection")
    model_mode = state.get("model_mode", "cloud")

    logger.info(f"📄 [Ingestion] 开始数据摄入...")

    # 如果已有 pdf_collection，跳过解析
    if pdf_collection is not None:
        logger.info(f"   [Ingestion] 已有 PDF 集合，跳过解析")
        cleaned_chunks = state.get("cleaned_chunks", [])
        return {"cleaned_chunks": cleaned_chunks}

    # 从文件路径解析 PDF
    pdf_path = state.get("pdf_path", "")
    if not pdf_path:
        logger.warning(f"   [Ingestion] 无 PDF 文件路径，跳过")
        return {"cleaned_chunks": []}

    try:
        raw_text = _extract_text_from_pdf(pdf_path)
        cleaned = _clean_text(raw_text)
        chunks = _chunk_text(cleaned)

        texts = [c["text"] for c in chunks]
        metadatas = [{"source": "PDF", "page": c.get("source_index", 0)} for c in chunks]

        collection = _build_pdf_collection(texts, metadatas, model_mode)

        logger.info(f"   ✅ 数据摄入完成: {len(chunks)} 个文本块")

        return {
            "cleaned_chunks": chunks,
            "pdf_collection": collection,
        }

    except Exception as e:
        logger.error(f"   ❌ 数据摄入失败: {e}")
        return {
            "cleaned_chunks": [],
            "error_message": f"PDF 解析失败: {str(e)}",
        }