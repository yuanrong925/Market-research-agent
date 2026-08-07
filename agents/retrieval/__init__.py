"""
agents/retrieval — RAG 混合检索与 Rerank 重排序模块

SOP 第二阶段核心：向量检索 + BM25 关键词检索 → 融合评分 → 交叉编码重排序
"""

from agents.retrieval.rag import (
    build_pdf_collection,
    query_pdf_collection,
    hybrid_search_collection,
    HybridRetriever,
    BM25Retriever,
)
from agents.retrieval.pdf_report import (
    generate_pdf_report,
)
from agents.retrieval.reranker import (
    rerank_results,
    rerank_hybrid_results,
)

__all__ = [
    "build_pdf_collection",
    "query_pdf_collection",
    "hybrid_search_collection",
    "generate_pdf_report",
    "HybridRetriever",
    "BM25Retriever",
    "rerank_results",
    "rerank_hybrid_results",
]