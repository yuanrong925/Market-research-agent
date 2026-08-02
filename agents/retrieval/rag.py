"""
agents/rag.py — 第二阶段：精准检索与降噪（Hybrid Search）

SOP 规范：
  1. 混合检索机制：向量检索（语义相关性）+ BM25关键词检索（精确术语匹配）
  2. Rerank重排序：交叉编码器深度相关性打分
  3. Top-K筛选：截取高置信度片段

外部依赖（可选）：
  - rank_bm25: pip install rank_bm25（纯 Python，无额外依赖）
  - 或使用内置的 TF-IDF 简单实现
"""
import hashlib
import json
import math
import os
import re
import uuid
from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Sequence
from urllib.request import Request, urlopen
from tools.logger import get_logger

logger = get_logger(__name__)


from chromadb import Client
from chromadb.config import Settings
from chromadb.utils import embedding_functions

from agents.config import (
    CLOUD_API_KEY,
    CLOUD_BASE_URL,
    DASHSCOPE_API_KEY,
    EMBEDDING_BASE_URL,
    EMBEDDING_MODEL,
    MODEL_MODE,
    OLLAMA_BASE_URL,
)

# Embedding 抽象层（可切换 dashscope / openai / local_bge）
from agents.providers.embedding import create_chroma_embedding_function

# ChromaDB 持久化目录
_CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")


def _file_hash(file_path: str) -> str:
    """计算文件的 MD5 哈希值，用于缓存去重"""
    h = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def create_chroma_client(persist_directory: Optional[str] = None) -> Client:
    if persist_directory:
        os.makedirs(persist_directory, exist_ok=True)
        settings = Settings(persist_directory=persist_directory, is_persistent=True)
        return Client(settings=settings)
    os.makedirs(_CHROMA_DIR, exist_ok=True)
    settings = Settings(persist_directory=_CHROMA_DIR, is_persistent=True)
    return Client(settings=settings)


# ============================================================
#  DashScope Embedding 类（已迁移到 embedding_provider，保留兼容）
# ============================================================

class DashScopeEmbeddingFunction:
    """
    [已弃用] 请使用 agents.embedding_provider.create_chroma_embedding_function()

    保留此类仅用于向后兼容，内部代理到新的 embedding_provider。
    """

    def __init__(self, api_key: str = "", model_name: str = "text-embedding-v3", api_base: str = ""):
        import warnings
        warnings.warn(
            "DashScopeEmbeddingFunction 已废弃，请使用 agents.embedding_provider.create_chroma_embedding_function('dashscope')",
            DeprecationWarning,
            stacklevel=2,
        )
        self._impl = create_chroma_embedding_function(provider='dashscope', model_name=model_name)

    def name(self):
        return "dashscope_embedding"

    def __call__(self, input: Any) -> List[List[float]]:
        return self._impl(input)

    def embed_query(self, *args, **kwargs) -> List[List[float]]:
        return self._impl.embed_query(*args, **kwargs)


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

        # 收集文档词频
        all_terms = set()
        for text in texts:
            terms = self._tokenize(text)
            freq = Counter(terms)
            self.doc_freqs.append(freq)
            self.doc_lens.append(len(terms))
            total_len += len(terms)
            all_terms.update(freq.keys())

        self.avg_doc_len = total_len / max(self.doc_count, 1)

        # 计算 IDF（逆向文档频率）
        # IDF(t) = ln(1 + (N - n_t + 0.5) / (n_t + 0.5))
        term_doc_count = Counter()
        for freq in self.doc_freqs:
            for term in freq:
                term_doc_count[term] += 1

        self.idf = {}
        for term, n_t in term_doc_count.items():
            self.idf[term] = math.log(1 + (self.doc_count - n_t + 0.5) / (n_t + 0.5))

    def _tokenize(self, text: str) -> List[str]:
        """中文分词：基于字符 + 简单英文分词"""
        # 中文：按字符切分（单字作为 token）
        # 英文：按空白/标点切分
        text = text.lower()
        tokens = []

        # 匹配中文字符
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        tokens.extend(chinese_chars)

        # 匹配英文单词/数字（长度≥2）
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
            # BM25 公式
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / self.avg_doc_len)
            score += idf_val * numerator / denominator

        return score

    def query(self, query: str, n_results: int = 10) -> List[tuple]:
        """
        用 BM25 检索 top-n 匹配的文档。

        返回:
          [(score, doc_index, text), ...] 按得分降序排列
        """
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

        # 构建 BM25 索引（仅当文本足够时）
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
        """
        执行混合检索（向量 + BM25），返回融合评分后的结果。

        参数:
          query: 查询
          n_results: 返回结果数量
          vector_weight: 向量检索得分权重（默认 0.6）
          bm25_weight: BM25 检索得分权重（默认 0.4）

        返回:
          [{ "text": str, "score": float, "vector_score": float, "bm25_score": float,
             "vector_rank": int, "bm25_rank": int, "metadata": dict, "source_index": int }, ...]
        """
        vector_results = self._vector_search(query, n_results * 2)
        bm25_results = self._bm25_search(query, n_results * 2)

        # 融合评分（保留原始分 / 原始排名）
        merged = self._fusion_score(
            vector_results=vector_results,
            bm25_results=bm25_results,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )

        # 截取 Top-K
        merged = merged[:n_results]

        # 格式统一，保留两套独立分数
        return [
            {
                "text": item["text"],
                "score": item["score"],
                "vector_score": item.get("vector_score", 0.0),
                "bm25_score": item.get("bm25_score", 0.0),
                "vector_rank": item.get("vector_rank", 999),
                "bm25_rank": item.get("bm25_rank", 999),
                "metadata": item.get("metadata", {}),
                "source_index": item.get("source_index", -1),
                "source_type": "hybrid",
            }
            for item in merged
        ]

    def _vector_search(self, query: str, n_results: int) -> List[Dict[str, Any]]:
        """向量检索（ChromaDB）

        如果 chroma_collection 为 None 或不可用，静默返回空列表（不崩溃）。
        """
        results = []

        if self.chroma_collection is None:
            return results  # 无声返回，不警告

        try:
            col = self.chroma_collection
            if isinstance(col, dict):
                col = col.get("collection", col)

            if col is None:
                return results

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

                    # 余弦距离转相似度得分 (0-1)
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
                # 归一化 BM25 得分到 0-1 范围
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
        """
        融合向量和 BM25 的检索结果（加权融合 + 去重）

        使用 Reci
        procal Rank Fusion（RRF）策略：
          RRF_score(d) = w_v * rank_v(d)^{-1} + w_b * rank_b(d)^{-1}
        """
        # 建立文本到排序的映射
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

        # 计算融合得分
        fused = []
        for text, ranks in text_rank_map.items():
            vector_rank = ranks.get("vector_rank", len(vector_results) + 1)
            bm25_rank = ranks.get("bm25_rank", len(bm25_results) + 1)

            # RRF 公式: 1/(k + rank)
            k = 60
            rrf_score = (
                vector_weight * (1.0 / (k + vector_rank)) +
                bm25_weight * (1.0 / (k + bm25_rank))
            )

            # 保留两套独立分数（原始相似度 vs BM25 归一化得分）
            vector_score = ranks.get("vector_score", 0.0)
            bm25_score = ranks.get("bm25_score", 0.0)

            fused.append({
                "text": text,
                "score": rrf_score,
                "vector_score": vector_score,
                "bm25_score": bm25_score,
                "vector_rank": vector_rank,
                "bm25_rank": bm25_rank,
                "metadata": ranks.get("metadata", {}),
                "source_index": ranks.get("source_index", -1),
                "source_type": "hybrid",
            })

        # 按融合得分降序排列
        fused.sort(key=lambda x: x["score"], reverse=True)
        return fused


# ============================================================
#  保留旧接口兼容
# ============================================================

def build_pdf_collection(
    texts: List[str],
    metadatas: List[Dict[str, Any]],
    model_mode: str = MODEL_MODE,
    collection_name: Optional[str] = None,
    source_file: Optional[str] = None,
) -> Any:
    # 用文件哈希作为集合名，实现自动去重
    if source_file and os.path.exists(source_file):
        file_hash = _file_hash(source_file)
    else:
        file_hash = collection_name or uuid.uuid4().hex
    collection_name = f"pdf-{file_hash}"

    logger.info(f"   📚 构建 PDF 向量集合: {collection_name}, 文档数={len(texts)}, 来源={source_file or '内存'}")

    # ===== 先构建 HybridRetriever（BM25 索引肯定可用）======
    hybrid = HybridRetriever()
    hybrid.build_index(texts, metadatas)

    # ===== 尝试 Chroma（带重试+优雅降级）======
    collection = None
    chroma_ok = False
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            client = create_chroma_client()
            embedding_fn = create_chroma_embedding_function()

            col = client.get_or_create_collection(
                name=collection_name,
                embedding_function=embedding_fn,
            )

            # 检查集合是否已有数据，有则跳过添加（避免重复）
            if col.count() == 0:
                col.add(
                    ids=[f"doc-{i}" for i in range(len(texts))],
                    documents=texts,
                    metadatas=metadatas,
                )
                logger.info(f"   ✅ Chroma 集合已创建并添加 {len(texts)} 条文档: {collection_name}")
            else:
                logger.info(f"   ✅ Chroma 集合已存在（跳过重复添加）: {collection_name}, 当前文档数: {col.count()}")

            collection = col
            chroma_ok = True
            break  # 成功退出重试
        except Exception as exc:
            logger.warning(f"   ⚠️ Chroma 初始化失败 (attempt {attempt}/{max_retries}): {exc}")
            if attempt < max_retries:
                import time as _t
                _t.sleep(1)  # 重试前等待

    # 将 Chroma collection 关联到 HybridRetriever（如果成功）
    if chroma_ok and collection is not None:
        hybrid.chroma_collection = collection
        # 重新构建索引（此时能用到向量）
        hybrid.build_index(texts, metadatas, chroma_collection=collection)
        logger.info(f"   ✅ Chroma + BM25 混合索引构建完成: {collection_name}")
        return {
            "type": "chroma",
            "collection": collection,
            "hybrid": hybrid,
            "chroma_ok": True,
        }

    # Chroma 完全失败 → 纯 BM25 模式（不降级到简陋内存检索）
    logger.warning(f"   ⚠️ Chroma 初始化失败（{max_retries} 次重试后仍不可用），使用纯 BM25 模式")
    logger.info(f"   ✅ BM25 索引已就绪: {len(texts)} 条文档（无向量索引）")
    return {
        "type": "bm25_only",
        "texts": texts,
        "metadatas": metadatas,
        "hybrid": hybrid,
        "chroma_ok": False,
    }


def query_pdf_collection(collection: Any, query: str, n_results: int = 3) -> List[str]:
    """
    使用混合检索查询 PDF 集合（向量 + BM25）。
    这是 SOP 第二阶段的核心入口。
    """
    retrieved: List[str] = []

    if collection is None:
        return retrieved

    # 统一通过 HybridRetriever 检索
    hybrid = None
    if isinstance(collection, dict):
        hybrid = collection.get("hybrid")

    # 使用 hybrid_search 获取结构化结果
    if hybrid and isinstance(hybrid, HybridRetriever):
        try:
            results = hybrid.hybrid_search(query, n_results=n_results)
            for item in results:
                text = item["text"]
                meta = item.get("metadata", {})
                source = meta.get("source", "PDF")
                page = meta.get("page")
                tag = f"[{source} - 页 {page}]" if page is not None else f"[{source}]"
                retrieved.append(f"{tag} {text}")
            return retrieved
        except Exception as e:
            logger.warning(f"   ⚠️ HybridRetriever 查询失败，回退: {e}")

    # === 回退：Chroma-only 查询（保留旧版兼容） ===
    if isinstance(collection, dict) and collection.get("type") == "chroma":
        col = collection.get("collection")
        try:
            results = col.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas"],
            )
            docs = results.get("documents") or []
            metadatas = results.get("metadatas") or []
            if docs and isinstance(docs, list):
                for idx, doc in enumerate(docs[0] if docs and isinstance(docs[0], list) else docs):
                    meta = metadatas[0][idx] if metadatas and isinstance(metadatas[0], list) and idx < len(metadatas[0]) else {}
                    source = meta.get("source", "PDF")
                    page = meta.get("page")
                    tag = f"[{source} - 页 {page}]" if page is not None else f"[{source}]"
                    retrieved.append(f"{tag} {doc}")
        except Exception:
            return []

    # === 纯 BM25 模式（Chroma 不可用时的降级） ===
    elif isinstance(collection, dict) and collection.get("type") == "bm25_only":
        texts = collection.get("texts", [])
        metadatas = collection.get("metadatas", [])
        if hybrid and isinstance(hybrid, HybridRetriever) and hybrid.bm25:
            try:
                bm25_hits = hybrid.bm25.query(query, n_results=n_results)
                for score, idx, text in bm25_hits:
                    meta = metadatas[idx] if idx < len(metadatas) else {}
                    source = meta.get("source", "PDF")
                    page = meta.get("page")
                    tag = f"[{source} - 页 {page}]" if page is not None else f"[{source}]"
                    retrieved.append(f"{tag} {text}")
                return retrieved
            except Exception as e:
                logger.warning(f"   ⚠️ BM25 查询失败: {e}")

    return retrieved


def hybrid_search_collection(
    collection: Any,
    query: str,
    n_results: int = 5,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    SOP 第二阶段核心接口：混合检索 + 评分融合。

    返回带有评分的结构化结果，可直接送 Rerank 模块做二次排序。
    """
    if collection is None:
        return []

    collection_type = ""
    hybrid = None
    if isinstance(collection, dict):
        collection_type = collection.get("type", "")
        hybrid = collection.get("hybrid")

    if hybrid and isinstance(hybrid, HybridRetriever):
        # bm25_only 模式降低向量权重（因为没有向量索引）
        if collection_type == "bm25_only":
            adjusted_vw = 0.0
            adjusted_bw = 1.0
            logger.info(f"   🔄 纯 BM25 模式: 权重调整为 vector=0.0, bm25=1.0")
        else:
            adjusted_vw, adjusted_bw = vector_weight, bm25_weight

        return hybrid.hybrid_search(query, n_results=n_results,
                                    vector_weight=adjusted_vw, bm25_weight=adjusted_bw)

    # 无 HybridRetriever 时，降级用旧版 query_pdf_collection
    texts = query_pdf_collection(collection, query, n_results=n_results)
    return [
        {"text": t, "score": 1.0, "source_type": "fallback"}
        for t in texts
    ]


# ============================================================
#  PDF 生成（保持不变）
# ============================================================

def generate_pdf_report(report_json: Any, output_path: str) -> str:
    """
    生成简洁的 PDF 报告。
    标题用大字号，发现/结论/建议用缩进区分层级，没有花哨渲染。
    """
    if isinstance(report_json, str):
        try:
            import json
            report_json = json.loads(report_json)
        except Exception:
            return _plaintext_fallback(report_json, output_path)
    if not isinstance(report_json, dict):
        return _plaintext_fallback(str(report_json), output_path)

    import fitz, os as _os
    doc = fitz.open()
    fn = _get_cjk_font_name()
    font = fitz.Font(fontname=fn)
    pw, ph = 595, 842
    ml, mr, mt, mb = 45, 45, 40, 40
    cw = pw - ml - mr

    def new_page():
        return doc.new_page()

    # 行高常量（用于分页判断）
    _LINE_GAP = 4

    def write(x, y, text, size=10, color=(0,0,0)):
        # 单行文本写入，由调用方负责分页判断
        # （参数 y 是局部变量，不可用 nonlocal 修改外层 y）
        doc[-1].insert_text((x, y), text, fontsize=size, fontname=fn, color=color)

    def wrap(text, size, max_w, font=None):
        """
        按最大宽度换行，返回行列表。
        自动分页由 render() 处理。

        策略：
          1. 优先使用 font.text_length() 精确测量宽度（兼容 CJK）
          2. 如果 font 不支持 CJK（text_length 返回异常值或为 0），
             降级到字符宽度系数估算（中文字符=1.0em，英文=0.5em）
          3. 对过长的段落，用二分查找加速，避免 O(n²) 退化为 O(n log n)
          4. 极端兜底：单行实在放不下时强制截断一个字符
        """
        lines = []
        if not text:
            return lines

        # 检测 font 是否真正支持 CJK：用中文测试字符串测量
        font_supports_cjk = False
        if font is not None:
            try:
                test_w = font.text_length("中文测试", size)
                font_supports_cjk = (test_w > 10)
            except Exception:
                font_supports_cjk = False

        def _line_width(line: str) -> float:
            """计算一行文本的宽度，自适应 font 支持情况"""
            if font is not None and font_supports_cjk:
                try:
                    return font.text_length(line, size)
                except Exception:
                    pass
            # 降级估算：CJK 字符 ≈ 1.0em，ASCII ≈ 0.5em
            w = 0.0
            for ch in line:
                if ord(ch) > 127:
                    w += size * 1.0  # CJK 字符
                else:
                    w += size * 0.5  # ASCII 字符
            return w

        # 安全兜底：确保 max_w 至少为 size * 2，防止不受限
        if max_w < size * 2:
            max_w = size * 2

        while text:
            n = len(text)
            # 整行能放下 → 直接整行
            if _line_width(text) <= max_w:
                lines.append(text)
                break

            # 二分查找最大可容纳字符数
            lo, hi = 1, n
            while lo < hi:
                mid = (lo + hi + 1) // 2
                try:
                    w = _line_width(text[:mid])
                    if w <= max_w:
                        lo = mid
                    else:
                        hi = mid - 1
                except Exception:
                    # 任何异常都缩小范围
                    hi = mid - 1
            if lo == 0:
                lo = 1  # 极端兜底：至少截取一个字符
            lines.append(text[:lo])
            text = text[lo:]

        return lines

    def render(text, x, y, size=10, indent=0, max_w=None, color=(0,0,0)):
        """渲染多行并返回下一个y，自动分页"""
        # 参数 y 是局部变量，不可用 nonlocal
        if max_w is None:
            max_w = cw - indent
        # 安全兜底：至少保证 cw 的 40%，防止缩进过大导致溢出
        min_max_w = int(cw * 0.4)
        if max_w < min_max_w:
            max_w = min_max_w
        lines = wrap(text, size, max_w, font)
        for line in lines:
            line_h = size + _LINE_GAP
            # 检查下一行是否能放下 → 不能则分页
            if y + line_h > ph - mb:
                new_page()
                y = mt
            doc[-1].insert_text((x + indent, y), line, fontsize=size, fontname=fn, color=color)
            y += line_h
        return y

    # ========== 开始 ==========
    page = new_page()
    y = mt

    # 标题
    title = report_json.get("标题") or report_json.get("title") or "分析报告"
    write(ml, y, title, 18, (0.05, 0.20, 0.40))
    y += 26
    # 分隔线
    doc[-1].draw_line((ml, y), (pw - mr, y), color=(0.3, 0.6, 0.9), width=0.8)
    y += 12

    # 摘要
    s = report_json.get("摘要") or report_json.get("summary")
    if s:
        if y > ph - mb - 30:
            new_page(); y = mt
        write(ml, y, "【执行摘要】", 12, (0.05, 0.20, 0.40))
        y += 16
        y = render(s, ml, y, 10, 8)
        y += 6

    # 背景
    bg = report_json.get("背景") or report_json.get("background")
    if bg:
        if y > ph - mb - 30:
            new_page(); y = mt
        write(ml, y, "【研究背景】", 12, (0.05, 0.20, 0.40))
        y += 16
        y = render(bg, ml, y, 10, 8)
        y += 6

    # 关键发现
    findings = report_json.get("关键发现") or report_json.get("key_findings") or []
    if findings:
        if y > ph - mb - 40:
            new_page(); y = mt
        write(ml, y, "【关键发现】", 14, (0.05, 0.20, 0.40))
        y += 20
        for idx, f in enumerate(findings):
            if y > ph - mb - 40:
                new_page(); y = mt
            topic = f.get("主题") or f.get("topic") or f"发现 {idx+1}"
            detail = f.get("详情") or f.get("detail") or ""
            evidence = f.get("证据") or f.get("evidence") or []

            y = render(f"{idx+1}. {topic}", ml, y, 11, indent=0)
            y += 2

            if detail:
                y = render(detail, ml, y, 10, indent=12)
                y += 1

            if evidence:
                for ev in evidence:
                    if y > ph - mb - 20:
                        new_page(); y = mt
                    y = render(ev, ml, y, 9, indent=12, color=(0.35, 0.35, 0.35))
                y += 1
            y += 3

    # 结论
    cons = report_json.get("结论") or report_json.get("conclusions") or []
    if cons:
        if y > ph - mb - 50:
            new_page(); y = mt
        write(ml, y, "【结论】", 14, (0.05, 0.20, 0.40))
        y += 20
        for c in cons:
            if y > ph - mb - 20:
                new_page(); y = mt
            y = render(c, ml, y, 10, indent=8)
        y += 4

    # 建议
    recs = report_json.get("建议") or report_json.get("recommendations") or []
    if recs:
        if y > ph - mb - 50:
            new_page(); y = mt
        write(ml, y, "【建议】", 14, (0.05, 0.20, 0.40))
        y += 20
        for r in recs:
            if y > ph - mb - 20:
                new_page(); y = mt
            y = render(r, ml, y, 10, indent=8)
        y += 4

    # 引用来源
    refs = report_json.get("引用来源") or report_json.get("references") or []
    if refs:
        if y > ph - mb - 50:
            new_page(); y = mt
        write(ml, y, "【引用来源】", 14, (0.05, 0.20, 0.40))
        y += 20
        for i, ref in enumerate(refs):
            if y > ph - mb - 20:
                new_page(); y = mt
            y = render(f"  [{i+1}] {ref}", ml, y, 9, 8, color=(0.35, 0.35, 0.35))

    # 页码
    for i in range(doc.page_count):
        pw_i, ph_i = pw, ph
        doc[i].insert_text((pw_i - 50, ph_i - 25), str(i + 1), fontsize=8, fontname=fn, color=(0.7, 0.7, 0.7))

    _os.makedirs(_os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path


def _plaintext_fallback(text: str, output_path: str) -> str:
    """
    纯文本回退，安全分页排版。
    使用字符宽度系数估算换行，每行严格检查是否超出页面，超出则自动分页。
    """
    import fitz, os as _os
    doc = fitz.open()
    fn = _get_cjk_font_name()
    pw, ph = 595, 842
    margin = 50
    max_line_w = pw - 2 * margin - 10  # 最大行宽（预留安全边距）
    font_size = 10
    line_height = font_size + 4       # 行高
    content_h = ph - 2 * margin       # 内容区高度
    max_lines_per_page = int(content_h / line_height)

    page = doc.new_page()
    lines_on_page = 0

    def _char_width(ch: str) -> float:
        return font_size * 0.85 if ord(ch) > 127 else font_size * 0.45

    def _split_line(text: str) -> str:
        """按宽度截取一行，确保不超 max_line_w"""
        w = 0.0
        for i, ch in enumerate(text):
            cw = _char_width(ch)
            if w + cw > max_line_w:
                return text[:i] if i > 0 else text[:1]
            w += cw
        return text

    for para in text.replace("\r\n", "\n").split("\n"):
        if not para.strip():
            lines_on_page += 1
            if lines_on_page >= max_lines_per_page:
                page = doc.new_page()
                lines_on_page = 0
            continue

        remaining = para
        while remaining:
            if lines_on_page >= max_lines_per_page:
                page = doc.new_page()
                lines_on_page = 0
            line = _split_line(remaining)
            page.insert_text(
                (margin, margin + lines_on_page * line_height),
                line, font_size, fontname=fn, color=(0, 0, 0)
            )
            remaining = remaining[len(line):]
            lines_on_page += 1

    doc.save(output_path)
    doc.close()
    return output_path


def _get_cjk_font_name() -> str:
    """
    选择一个支持中文的字体。
    优先使用 PyMuPDF 内置 CJK 字体 china-s，如果不可用则尝试其他方案。
    最终回退到 'helv' (PyMuPDF 内置无衬线体)，配合字符数估算换行。
    """
    import os as _os
    import platform as _platform
    import fitz

    # 1. 尝试 PyMuPDF 内置 CJK 字体
    # 注：china-ss (sans-serif) 的 ASCII 字符宽度比例更优，优先使用
    builtin_fonts = ["china-ss", "china-s", "china-st", "china-t", "DroidSansFallback"]
    for name in builtin_fonts:
        try:
            f = fitz.Font(fontname=name)
            # 验证是否真的支持中文
            tw = f.text_length("中国测试中文", fontsize=12)
            if tw > 10:
                return name
        except Exception:
            continue

    # 2. 尝试 fonts/ 目录下的自定义字体
    base_dir = _os.path.dirname(_os.path.abspath(__file__))
    project_dir = _os.path.dirname(base_dir)
    fonts_dir = _os.path.join(project_dir, "fonts")
    if _os.path.isdir(fonts_dir):
        for fname in sorted(_os.listdir(fonts_dir)):
            if fname.lower().endswith((".ttf", ".ttc", ".otf")):
                fpath = _os.path.join(fonts_dir, fname)
                try:
                    f = fitz.Font(fontfile=fpath)
                    tw = f.text_length("中国测试中文", fontsize=12)
                    if tw > 10:
                        return fpath
                except Exception:
                    continue

    # 3. 尝试系统字体 (Windows)
    if _platform.system() == "Windows":
        win_dir = _os.environ.get("WINDIR", "C:\\Windows")
        sys_fonts = [
            _os.path.join(win_dir, "Fonts", "msyh.ttc"),
            _os.path.join(win_dir, "Fonts", "simsun.ttc"),
            _os.path.join(win_dir, "Fonts", "simhei.ttf"),
        ]
        for fp in sys_fonts:
            if _os.path.exists(fp):
                try:
                    f = fitz.Font(fontfile=fp)
                    tw = f.text_length("中国测试中文", fontsize=12)
                    if tw > 10:
                        return fp
                except Exception:
                    continue

    # 4. 尝试下载 Noto Sans SC 字体到 fonts/ 目录
    try:
        _os.makedirs(fonts_dir, exist_ok=True)
        cached = _os.path.join(fonts_dir, "NotoSansSC-Regular.otf")
        if _os.path.exists(cached) and _os.path.getsize(cached) > 10000:
            try:
                f = fitz.Font(fontfile=cached)
                tw = f.text_length("中国测试中文", fontsize=12)
                if tw > 10:
                    return cached
            except Exception:
                pass

        # 直接从 CDN 下载 OTF 文件（小文件，无 ZIP 解压，添加超时防卡死）
        import urllib.request
        import socket
        socket.setdefaulttimeout(10)
        urls = [
            "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@v2.004/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
            "https://raw.githubusercontent.com/notofonts/noto-cjk/v2.004/Sans/OTF/SimplifiedChinese/NotoSansSC-Regular.otf",
        ]
        for url in urls:
            try:
                logger.info(f"   Downloading Noto Sans SC font: {url[:50]}...")
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                if len(data) > 10000:
                    with open(cached, "wb") as f:
                        f.write(data)
                    f = fitz.Font(fontfile=cached)
                    tw = f.text_length("Chinese test", fontsize=12)
                    if tw > 10:
                        logger.info(f"   Successfully downloaded Noto Sans SC font: {cached}")
                        return cached
            except Exception as e:
                logger.debug(f"   Font download failed: {e}")
                if _os.path.exists(cached):
                    try:
                        _os.remove(cached)
                    except Exception:
                        pass
                continue
    except Exception:
        pass

    # 5. 尝试 fc-list 查找系统中文字体
    try:
        import subprocess as _sp
        result = _sp.run(['fc-list', ':lang=zh', '-f', '%{file}\n'],
                         capture_output=True, text=True, timeout=5)
        for fp in result.stdout.strip().split('\n'):
            fp = fp.strip()
            if fp and fp.endswith(('.ttf', '.ttc', '.otf')):
                try:
                    f = fitz.Font(fontfile=fp)
                    tw = f.text_length("中国测试中文", fontsize=12)
                    if tw > 10:
                        return fp
                except Exception:
                    continue
    except Exception:
        pass

    # 6. 最终回退
    # 注意：china-ss 是等宽 CJK 字体，ASCII 字符会比标准比例字体宽，
    # 如果希望字母间距更紧凑，请安装 Noto Sans SC 等比例字体到 fonts/ 目录
    logger.warning("   ⚠️ 未找到中文字体，回退到 china-ss（ASCII 字符为等宽，字母间距可能偏大）")
    return "china-ss"
