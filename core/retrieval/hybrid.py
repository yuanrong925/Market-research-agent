"""
混合检索引擎 — BM25 关键词检索 + 向量检索融合评分

SOP 第二阶段核心引擎：
  1. 向量检索（语义相关性）
  2. BM25 关键词检索（精确匹配）
  3. 融合评分（RRF 策略）
  4. 配合外部 Rerank 模块
"""

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from core.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
#  BM25 关键词检索（纯 Python 实现）
# ============================================================

class BM25Retriever:
    """
    BM25 关键词检索器。
    用于与向量检索并行执行，捕捉精确术语匹配。

    参数:
      k1: BM25 参数，控制词频饱和度（默认 1.5）
      b: BM25 参数，控制文档长度归一化（默认 0.75）
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus: List[str] = []
        self.avg_doc_len: float = 0.0
        self.doc_count: int = 0
        self.doc_freqs: List[Counter] = []
        self.idf: Dict[str, float] = {}
        self.doc_lens: List[int] = []

    def fit(self, texts: List[str]) -> None:
        """用文档语料拟合 BM25 参数"""
        self.corpus = texts
        self.doc_count = len(texts)
        self.doc_freqs = []
        self.doc_lens = []
        total_len = 0

        all_terms = set()
        for text in texts:
            terms = self._tokenize(text)
            freq = Counter(terms)
            self.doc_freqs.append(freq)
            self.doc_lens.append(len(terms))
            total_len += len(terms)
            all_terms.update(freq.keys())

        self.avg_doc_len = total_len / max(self.doc_count, 1)

        term_doc_count = Counter()
        for freq in self.doc_freqs:
            for term in freq:
                term_doc_count[term] += 1

        self.idf = {}
        for term, n_t in term_doc_count.items():
            self.idf[term] = math.log(1 + (self.doc_count - n_t + 0.5) / (n_t + 0.5))

    def _tokenize(self, text: str) -> List[str]:
        """中文分词：基于字符 + 简单英文分词"""
        text = text.lower()
        tokens = []
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)
        eng_tokens = re.findall(r'[a-z0-9]{2,}', text)
        tokens.extend(eng_tokens)
        return tokens

    def score(self, query: str, doc_index: int) -> float:
        """计算查询与文档之间的 BM25 得分"""
        query_terms = self._tokenize(query)
        doc_freq = self.doc_freqs[doc_index]
        doc_len = self.doc_lens[doc_index]

        score = 0.0
        for term in set(query_terms):
            if term not in self.idf:
                continue
            tf = doc_freq.get(term, 0)
            if tf == 0:
                continue

            idf_val = self.idf[term]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
            score += idf_val * numerator / denominator

        return score

    def query(self, query: str, n_results: int = 10) -> List[tuple]:
        """用 BM25 检索 top-n 匹配的文档"""
        scores = []
        for i in range(self.doc_count):
            s = self.score(query, i)
            if s > 0:
                scores.append((s, i, self.corpus[i]))

        scores.sort(reverse=True, key=lambda x: x[0])
        return scores[:n_results]


# ============================================================
#  混合检索引擎
# ============================================================

class HybridRetriever:
    """
    SOP 第二阶段核心引擎：
      1. 向量检索（语义相关性）
      2. BM25 关键词检索（精确匹配）
      3. 融合评分
      4. 配合外部 Rerank 模块
    """

    def __init__(self, chroma_collection: Optional[Any] = None):
        self.chroma_collection = chroma_collection
        self.bm25: Optional[BM25Retriever] = None
        self.all_texts: List[str] = []
        self.all_metadatas: List[Dict[str, Any]] = []

    def build_index(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        chroma_collection: Optional[Any] = None,
    ) -> None:
        """构建向量 + BM25 联合索引"""
        self.all_texts = texts
        self.all_metadatas = metadatas

        if chroma_collection:
            self.chroma_collection = chroma_collection

        if len(texts) > 0:
            self.bm25 = BM25Retriever()
            self.bm25.fit(texts)
            logger.info(f"   📊 BM25 索引构建完成: {len(texts)} 篇文档")

    def hybrid_search(
        self,
        query: str,
        n_results: int = 10,
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> List[Dict[str, Any]]:
        """执行混合检索（向量 + BM25），返回融合评分后的结果"""
        vector_results = self._vector_search(query, n_results * 2)
        bm25_results = self._bm25_search(query, n_results * 2)

        merged = self._fusion_score(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )

        merged = merged[:n_results]

        return [
            {
                "text": item["text"],
                "score": item["score"],
                "metadata": item.get("metadata", {}),
                "source_index": item.get("source_index", -1),
                "source_type": "hybrid",
            }
            for item in merged
        ]

    def _vector_search(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        """向量检索（ChromaDB）"""
        results = []

        if self.chroma_collection:
            try:
                col = self.chroma_collection
                if isinstance(col, dict):
                    col = col.get("collection", col)

                resp = col.query(
                    query_texts=[query],
                    n_results=n_results,
                    include=["documents", "metadatas", "distances"],
                )
                docs = resp.get("documents", []) or []
                metas = resp.get("metadatas", []) or []
                dists = resp.get("distances", []) or []

                if docs and isinstance(docs, list):
                    for i, doc in enumerate(docs[0] if isinstance(docs[0], list) else docs):
                        meta = {}
                        if metas and isinstance(metas[0], list) and i < len(metas[0]):
                            meta = metas[0][i]
                        dist = 0.0
                        if dists and isinstance(dists[0], list) and i < len(dists[0]):
                            dist = dists[0][i]

                        similarity = 1.0 - dist if dist < 1.0 else 0.0

                        results.append({
                            "text": doc,
                            "score": similarity,
                            "metadata": meta,
                            "source_index": i,
                            "source_type": "vector",
                        })
            except Exception as e:
                logger.warning(f"   ⚠️ 向量检索失败: {e}")

        return results

    def _bm25_search(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        """BM25 关键词检索"""
        results = []

        if self.bm25 is None:
            return results

        try:
            bm25_hits = self.bm25.query(query, n_results=n_results)
            for score, idx, text in bm25_hits:
                norm_score = min(score / 10.0, 1.0) if score > 0 else 0.0

                meta = {}
                if idx < len(self.all_metadatas):
                    meta = self.all_metadatas[idx]

                results.append({
                    "text": text,
                    "score": norm_score,
                    "metadata": meta,
                    "source_index": idx,
                    "source_type": "bm25",
                })
        except Exception as e:
            logger.warning(f"   ⚠️ BM25 检索失败: {e}")

        return results

    def _fusion_score(
        self,
        vector_results: List[Dict[str, Any]],
        bm25_results: List[Dict[str, Any]],
        vector_weight: float = 0.6,
        bm25_weight: float = 0.4,
    ) -> List[Dict[str, Any]]:
        """融合向量和 BM25 的检索结果（加权融合 + 去重）"""
        text_rank_map: Dict[str, Dict[str, float]] = {}

        for rank, item in enumerate(vector_results):
            text = item["text"]
            if text not in text_rank_map:
                text_rank_map[text] = {}
            text_rank_map[text]["vector_rank"] = rank + 1
            text_rank_map[text]["vector_score"] = item["score"]
            text_rank_map[text]["metadata"] = item.get("metadata", {})
            text_rank_map[text]["source_index"] = item.get("source_index", -1)

        for rank, item in enumerate(bm25_results):
            text = item["text"]
            if text not in text_rank_map:
                text_rank_map[text] = {}
            text_rank_map[text]["bm25_rank"] = rank + 1
            text_rank_map[text]["bm25_score"] = item["score"]
            text_rank_map[text].setdefault("metadata", item.get("metadata", {}))
            text_rank_map[text].setdefault("source_index", item.get("source_index", -1))

        fused = []
        for text, ranks in text_rank_map.items():
            vector_rank = ranks.get("vector_rank", len(vector_results) + 1)
            bm25_rank = ranks.get("bm25_rank", len(bm25_results) + 1)

            k = 60
            rrf_score = (
                vector_weight * (1.0 / (k + vector_rank)) +
                bm25_weight * (1.0 / (k + bm25_rank))
            )

            fused.append({
                "text": text,
                "score": rrf_score,
                "metadata": ranks.get("metadata", {}),
                "source_index": ranks.get("source_index", -1),
                "source_type": "hybrid",
            })

        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused