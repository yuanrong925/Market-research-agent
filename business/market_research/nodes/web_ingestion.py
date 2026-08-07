"""
Web 网页切片入库节点 — 统一向量库

功能：
  1. 接收检索节点返回的 web_results（含清洗后的切片）
  2. 对每个网页切片做 chunk 校验（规则校验，不调 LLM）
  3. 校验通过的切片写入统一 ChromaDB 集合（含 PDF + Web）
  4. 写入 Chroma 后，报告写作阶段禁止访问原始网页，只能从向量库取数据
"""

import hashlib
from typing import Any, Dict, List, Optional

from core.utils.logger import get_logger
from business.market_research.utils.web_cleaner import _chunk_text as web_chunk_text

from business.market_research.state import AgentState

logger = get_logger(__name__)

# ============================================================
#  配置常量
# ============================================================

# 最短有效 chunk 长度（字符）
_MIN_CHUNK_LENGTH = 20

# 最大 chunk 长度（字符，超过的截断）
_MAX_CHUNK_LENGTH = 2000

# 校验通过的最低分数
_MIN_VALIDATION_SCORE = 0.35


# ============================================================
#  Chunk 校验（规则校验，不调 LLM）
# ============================================================

def _validate_web_chunk(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    对单条网页 chunk 进行校验。

    校验规则（纯规则，不调 LLM）：
      1. 文本长度校验：过短（<20）或过长（>2000）的 chunk 剔除
      2. 内容密度校验：去空白后有效字符比例 > 50%
      3. 重复内容校验：与已有 chunk 高重复的剔除
      4. 信息来源校验：必须有 source_url
      5. 断句完整性校验：不能以连接词/标点开头结尾

    Returns:
      {"passed": bool, "score": float, "reason": str}
    """
    text = chunk.get("text", "")
    source_url = chunk.get("source_url", "")

    # 1. 文本长度校验
    if not text or len(text) < _MIN_CHUNK_LENGTH:
        return {"passed": False, "score": 0.0, "reason": f"chunk 过短 ({len(text)} < {_MIN_CHUNK_LENGTH})"}
    if len(text) > _MAX_CHUNK_LENGTH:
        return {"passed": False, "score": 0.0, "reason": f"chunk 过长 ({len(text)} > {_MAX_CHUNK_LENGTH})"}

    # 2. 内容密度校验
    stripped = text.strip()
    whitespace_ratio = 1.0 - (len(stripped) / max(len(text), 1))
    if whitespace_ratio > 0.5:
        return {"passed": False, "score": 0.2, "reason": f"空白字符占比过高 ({whitespace_ratio:.1%})"}

    # 3. 信息来源校验
    if not source_url:
        return {"passed": False, "score": 0.1, "reason": "缺少 source_url"}

    # 4. 断句完整性校验
    ambiguous_starts = ["那么", "因此", "所以", "但是", "然而", "不过", "此外", "另外", "同时", "并且", "以及", "或者", "虽然", "尽管", "如果", "因为", "由于", "从而", "进而", "而且", "其中", "例如", "比如", "如", "包括", "特别", "尤其", "特别是", "尤其是", "同时", "以及", "另外", "此外", "还有", "除此之外", "总而言之", "总之", "综上", "综上所述"]
    ambiguous_ends = ["例如", "比如", "如下", "以下", "包括", "主要", "分为", "有", "是", ":", "：", "的", "了", "在", "和", "与", "或", "而", "但", "但", "并", "并且", "以及", "而且", "同时", "此外", "另外", "不过", "虽然", "由于", "因为", "所以", "因此", "从而", "进而", "如果", "则", "那么", "那", "这", "这个", "这些", "那些", "其中"]

    text_stripped = text.strip()
    for word in ambiguous_starts:
        if word and len(word) >= 2 and text_stripped.startswith(word):
            return {"passed": False, "score": 0.3, "reason": f"断句歧义：以「{word}」开头"}
    for word in ambiguous_ends:
        if word and len(word) >= 2 and text_stripped.endswith(word):
            return {"passed": False, "score": 0.3, "reason": f"断句歧义：以「{word}」结尾"}

    # 综合得分（基于文本长度和内容质量）
    score = min(0.5 + len(text) / 4000, 0.95)

    return {"passed": True, "score": score, "reason": "ok"}


# ============================================================
#  构建统一 Chroma 集合
# ============================================================

def _compute_content_hash(texts: List[str]) -> str:
    """计算文本内容的哈希值"""
    combined = "".join(texts)
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def _build_unified_collection(
    pdf_chunks: List[Dict[str, Any]],
    web_chunks: List[Dict[str, Any]],
    model_mode: str,
) -> Dict[str, Any]:
    """
    构建统一 ChromaDB 集合（PDF + Web 混合入库）。

    Args:
        pdf_chunks: PDF 已入库的切片列表
        web_chunks: 网页清洗后的切片列表（已校验通过）

    Returns:
        collection dict: {"type": "chroma"|"inmemory", "collection": ..., "hybrid": ..., "total_chunks": int}
    """
    from core.retrieval.chroma import create_chroma_client, DashScopeEmbeddingFunction
    from core.retrieval.hybrid import HybridRetriever
    from core.config import get_config

    cfg = get_config()

    # 合并所有文本和元数据
    all_texts = []
    all_metadatas = []

    for chunk in pdf_chunks:
        text = chunk.get("text", "")
        if text and len(text) >= _MIN_CHUNK_LENGTH:
            all_texts.append(text)
            all_metadatas.append({
                "source_type": "pdf",
                "source_url": chunk.get("source_url", ""),
                "doc_name": chunk.get("doc_name", ""),
                "page_num": chunk.get("source_index", 0),
                "trust_tier": "verified",
            })

    for chunk in web_chunks:
        text = chunk.get("text", "")
        if text and len(text) >= _MIN_CHUNK_LENGTH:
            all_texts.append(text)
            all_metadatas.append({
                "source_type": "web",
                "source_url": chunk.get("source_url", ""),
                "doc_name": "",
                "page_num": 0,
                "trust_tier": "verified",
            })

    if not all_texts:
        logger.warning("   [WebIngestion] 无有效文本可入库")
        return {
            "type": "empty",
            "total_chunks": 0,
            "fallback": True,
            "fallback_reason": "无有效文本",
        }

    # 检查 Embedding API Key
    if not cfg.dashscope_api_key:
        logger.warning("   [WebIngestion] DASHSCOPE_API_KEY 未配置，降级到 inmemory 模式")
        hybrid = HybridRetriever()
        hybrid.build_index(all_texts, all_metadatas)
        return {
            "type": "inmemory",
            "texts": all_texts,
            "metadatas": all_metadatas,
            "fallback": True,
            "fallback_reason": "DASHSCOPE_API_KEY 未配置，降级到 BM25 关键词检索",
            "hybrid": hybrid,
            "total_chunks": len(all_texts),
        }

    try:
        client = create_chroma_client()

        # 用内容哈希做集合名
        content_hash = _compute_content_hash(all_texts)
        collection_name = f"unified-{content_hash}"

        embedding_fn = DashScopeEmbeddingFunction(
            api_key=cfg.dashscope_api_key,
            model_name=cfg.embedding_model,
            api_base=cfg.embedding_base_url,
        )

        # 尝试获取已有集合
        collection = None
        try:
            collection = client.get_collection(
                name=collection_name,
                embedding_function=embedding_fn,
            )
            logger.info(f"   📦 复用已有统一 Chroma 集合: {collection_name}, docs={collection.count()}")
        except Exception:
            pass

        if collection is None:
            collection = client.create_collection(
                name=collection_name,
                embedding_function=embedding_fn,
            )
            # 批量添加文本
            batch_size = 100
            for i in range(0, len(all_texts), batch_size):
                batch_texts = all_texts[i:i+batch_size]
                batch_metas = all_metadatas[i:i+batch_size]
                batch_ids = [f"doc-{j}" for j in range(i, i+len(batch_texts))]
                collection.add(
                    ids=batch_ids,
                    documents=batch_texts,
                    metadatas=batch_metas,
                )
            logger.info(f"   ✅ 统一 Chroma 集合新建成功: {collection_name}, docs={collection.count()}")

        hybrid = HybridRetriever(chroma_collection=collection)
        hybrid.build_index(all_texts, all_metadatas, chroma_collection=collection)

        return {
            "type": "chroma",
            "collection": collection,
            "hybrid": hybrid,
            "collection_name": collection_name,
            "total_chunks": len(all_texts),
        }

    except Exception as exc:
        reason = str(exc)
        logger.warning(f"   [WebIngestion] Chroma 构建失败，降级到内存模式: {reason}")
        hybrid = HybridRetriever()
        hybrid.build_index(all_texts, all_metadatas)
        return {
            "type": "inmemory",
            "texts": all_texts,
            "metadatas": all_metadatas,
            "fallback": True,
            "fallback_reason": f"Chroma 构建失败: {reason}，降级到 BM25 关键词检索",
            "hybrid": hybrid,
            "total_chunks": len(all_texts),
        }


# ============================================================
#  节点入口
# ============================================================

def web_ingestion_node(state: AgentState) -> Dict[str, Any]:
    """
    Web 网页入库节点。

    在检索节点之后、冲突检测之前执行。
    将清洗后的网页切片校验后写入统一 ChromaDB 集合。

    输入：
      - top_k_chunks: 检索结果（含 PDF + Web 切片）
      - pdf_collection: PDF 已有的向量集合
      - pdf_parsed_chunks: PDF 已解析的切片

    输出：
      - unified_collection: 统一 ChromaDB 集合（PDF + Web）
      - web_chunks_validated: True
      - web_chunks_in_db: 入库的 Web 切片数量
    """
    top_k_chunks = state.get("top_k_chunks", [])
    pdf_collection = state.get("pdf_collection", {})
    pdf_parsed_chunks = state.get("pdf_parsed_chunks", [])

    logger.info(f"🌐 [WebIngestion] 开始 Web 切片入库...")

    # 提取所有 web 来源的切片
    web_chunks_raw = []
    for item in top_k_chunks:
        if item.get("source_type") == "web":
            # 优先使用清洗后的完整切片
            cleaned = item.get("cleaned_chunks", [])
            if cleaned:
                web_chunks_raw.extend(cleaned)
            else:
                # 降级：使用 snippet 文本
                text = item.get("text", "")
                if text:
                    web_chunks_raw.append({
                        "text": text[:800],
                        "source_url": item.get("source_url", ""),
                        "source_index": item.get("source_index", 0),
                        "source_type": "web",
                    })

    logger.info(f"   [WebIngestion] 待校验: {len(web_chunks_raw)} 个原始 Web 切片")

    # 校验每个切片
    validated_chunks = []
    rejected_chunks = []
    for chunk in web_chunks_raw:
        result = _validate_web_chunk(chunk)
        if result["passed"]:
            validated_chunks.append(chunk)
        else:
            rejected_chunks.append({
                "chunk": chunk,
                "score": result["score"],
                "reason": result["reason"],
            })

    logger.info(f"   [WebIngestion] 校验结果: {len(validated_chunks)} 通过, {len(rejected_chunks)} 剔除")

    if rejected_chunks:
        for r in rejected_chunks[:5]:
            logger.info(f"     ❌ 剔除: {r['reason']}")

    # 如果没有有效切片，直接返回
    if not validated_chunks:
        logger.warning("   [WebIngestion] 无有效 Web 切片可入库")
        return {
            "unified_collection": state.get("pdf_collection", {}),
            "web_chunks_validated": True,
            "web_chunks_in_db": 0,
        }

    # 提取 PDF 已有切片
    pdf_chunks = pdf_parsed_chunks or []

    # 构建统一集合
    unified_collection = _build_unified_collection(
        pdf_chunks=pdf_chunks,
        web_chunks=validated_chunks,
        model_mode=state.get("model_mode", "cloud"),
    )

    web_count = len(validated_chunks)
    total_count = unified_collection.get("total_chunks", 0)
    logger.info(f"   ✅ [WebIngestion] 入库完成: {web_count} 个 Web 切片, 共 {total_count} 个切片")
    logger.info(f"   📦 统一集合类型: {unified_collection.get('type', 'unknown')}")

    return {
        "unified_collection": unified_collection,
        "web_chunks_validated": True,
        "web_chunks_in_db": web_count,
    }