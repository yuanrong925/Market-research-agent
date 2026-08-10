"""【Chunk 校验节点】— v2 精简版（仅 Layer 1 快速粗筛，移除 Layer 2 LLM 校验）

v2 精简变更：
  1. 移除 Layer 2 并发 LLM 语义校验（省去大量时间与Token）
  2. 移除「断句歧义检测」（导致合法 web 切片被全量过滤）
  3. BM25 相关性阈值从 0.45 降至 0.10（仅过滤完全无关内容）
  4. 仅保留：长度过滤、BM25 相关性过滤、去重、失真检测
  5. 节点总耗时从 60s+ 降至 < 2s
"""

import re
import time
from typing import Any, Dict, List, Tuple

from core.utils.logger import get_logger

logger = get_logger(__name__)


# ============================================================
#  校验阈值（v2 大幅放宽）
# ============================================================

# 最短 chunk 有效长度（字符数）
_MIN_CHUNK_LENGTH = 15
# 最长 chunk 截断（用于比对性能）
_MAX_CHUNK_FOR_COMPARE = 2000

# BM25 相关性阈值（低于此 → 不相关，丢弃）
# v2: 从 0.45 降至 0.10，仅过滤完全无关内容
_MIN_RELEVANCE_SCORE = 0.10
# 去重相似度阈值（高于此 → 视为重复，丢弃）
_MAX_DEDUP_SIMILARITY = 0.85

# N-gram 重叠率最低阈值（低于此 → 失真）
# v2.1: 从 0.30 降至 0.20，减少合法 web 切片误杀
_NGRAM_MIN_OVERLAP = 0.20
# 编辑距离比率最低阈值
_EDIT_DIST_RATIO_MIN = 0.25


# ============================================================
#  辅助函数
# ============================================================

def _normalize_text(text: str) -> str:
    """归一化文本"""
    text = text.lower()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[-，。！？、；：""''（）【】《》\n\r\t]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _compute_bm25_score(chunk_text: str, task_query: str) -> float:
    """基于关键词共现的简单 BM25 近似评分"""
    if not chunk_text or not task_query:
        return 0.0
    # 中文：单字符级匹配（解决 \u4e00-\u9fff\w+ 将连续中文匹配为整体 token 的问题）
    chunk_chars = set(re.findall(r'[\u4e00-\u9fff]', chunk_text.lower()))
    query_chars = set(re.findall(r'[\u4e00-\u9fff]', task_query.lower()))
    # 英文/数字：单词级匹配
    chunk_words = set(re.findall(r'[a-zA-Z0-9]+', chunk_text.lower()))
    query_words = set(re.findall(r'[a-zA-Z0-9]+', task_query.lower()))

    if not query_chars and not query_words:
        return 0.0

    char_overlap = len(chunk_chars & query_chars)
    word_overlap = len(chunk_words & query_words)

    char_score = char_overlap / (len(query_chars) + 0.001) if query_chars else 0.0
    word_score = word_overlap / (len(query_words) + 0.001) if query_words else 0.0

    return 0.7 * char_score + 0.3 * word_score


def _ngram_overlap(a: str, b: str, n: int = 5) -> float:
    """计算两个字符串的 N-gram 重叠比率"""
    if len(a) < n or len(b) < n:
        return 0.0
    a_grams = set(a[i:i+n] for i in range(len(a)-n+1))
    b_grams = set(b[i:i+n] for i in range(len(b)-n+1))
    if not a_grams or not b_grams:
        return 0.0
    intersection = a_grams & b_grams
    return len(intersection) / max(len(a_grams), len(b_grams))


def _levenshtein_ratio(a: str, b: str) -> float:
    """计算编辑距离比率"""
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    a = a[:_MAX_CHUNK_FOR_COMPARE]
    b = b[:_MAX_CHUNK_FOR_COMPARE]
    if a in b or b in a:
        short_len = min(len(a), len(b))
        long_len = max(len(a), len(b))
        return short_len / long_len if long_len > 0 else 0.0
    m, n = len(a), len(b)
    if m == 0 or n == 0:
        return 0.0
    prev = list(range(n + 1))
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            cost = 0 if a[i-1] == b[j-1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j-1] + 1,
                prev[j-1] + cost,
            )
        prev, curr = curr, prev
    distance = prev[n]
    max_len = max(m, n)
    return 1.0 - (distance / max_len) if max_len > 0 else 0.0


def _is_distorted(chunk_text: str, source_text: str) -> Tuple[bool, float, str]:
    """
    判断 chunk 是否失真（保留 N-gram + 编辑距离规则）。
    v2: 移除「断句歧义检测」，因为合法 web 切片常以"然而""因此"等开头。
    """
    norm_chunk = _normalize_text(chunk_text)
    norm_source = _normalize_text(source_text)

    if len(norm_chunk) < _MIN_CHUNK_LENGTH:
        return True, 0.0, "chunk 过短"
    if len(norm_source) < _MIN_CHUNK_LENGTH:
        return True, 0.0, "源文本过短，无法比对"

    # 1. N-gram 重叠率
    ngram = _ngram_overlap(norm_chunk, norm_source, n=5)

    # 2. 编辑距离比率
    edit_ratio = _levenshtein_ratio(norm_chunk, norm_source)

    # 3. 关键词覆盖率
    stop_words = {"的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
                  "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着",
                  "没有", "看", "好", "自己", "这", "他", "她", "它", "们"}
    chunk_words = set(re.findall(r'[\u4e00-\u9fff\w]+', norm_chunk))
    source_words = set(re.findall(r'[\u4e00-\u9fff\w]+', norm_source))
    content_words = chunk_words - stop_words
    if content_words:
        keyword_coverage = len(content_words & source_words) / len(content_words)
    else:
        keyword_coverage = 0.0

    # 综合得分（加权）
    score = 0.4 * ngram + 0.3 * edit_ratio + 0.3 * keyword_coverage

    # v2: 大幅放宽失真判定
    if ngram < _NGRAM_MIN_OVERLAP and edit_ratio < _EDIT_DIST_RATIO_MIN:
        return True, score, f"N-gram={ngram:.2f} < {_NGRAM_MIN_OVERLAP}, edit={edit_ratio:.2f} < {_EDIT_DIST_RATIO_MIN}，严重失真"

    if score < 0.20:
        return True, score, f"综合得分={score:.2f} < 0.20，脱离原文"

    return False, score, ""


# ============================================================
#  Layer 1 — 无 LLM 快速粗筛
# ============================================================

def _layer1_fast_filter(
    chunks: List[Dict[str, Any]],
    task: str,
    pdf_full_text: str,
    web_full_texts: Dict[str, str],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Layer 1：无 LLM 快速粗筛。

    过滤规则：
      1. 长度 < 15 字符 → 残缺，丢弃
      2. BM25 相关性 < 0.45 → 不相关，丢弃
      3. 与已通过 chunk 相似度 > 0.92 → 重复，丢弃
      4. N-gram + 编辑距离规则校验 → 失真/歧义，丢弃

    Returns:
      (candidates, rejected)
        - candidates: 通过 Layer 1 的候选 chunk
        - rejected: 被 Layer 1 过滤的 chunk
    """
    candidates = []
    rejected = []

    for chunk in chunks:
        chunk_text = chunk.get("text", "")
        source_type = chunk.get("source_type", "unknown")

        # 1. 长度过滤
        if not chunk_text or len(chunk_text.strip()) < _MIN_CHUNK_LENGTH:
            logger.debug(f"   [Validation] 过短: chunk[:50]={chunk_text[:50]!r}")
            rejected.append({**chunk, "layer1_reason": "残缺：chunk 过短", "layer1_score": 0.0})
            continue

        # 2. BM25 相关性过滤
        bm25_score = _compute_bm25_score(chunk_text, task)
        if bm25_score < _MIN_RELEVANCE_SCORE:
            logger.debug(f"   [Validation] BM25 过滤: score={bm25_score:.4f} < {_MIN_RELEVANCE_SCORE}, chunk[:50]={chunk_text[:50]!r}")
            rejected.append({**chunk, "layer1_reason": f"不相关：BM25={bm25_score:.2f} < {_MIN_RELEVANCE_SCORE}", "layer1_score": bm25_score})
            continue

        # 3. 去重（与已通过 chunk 比较）
        is_duplicate = False
        for passed in candidates:
            passed_text = passed.get("text", "")
            if not passed_text or not chunk_text:
                continue
            # 使用 N-gram 重叠率近似相似度
            sim = _ngram_overlap(
                _normalize_text(chunk_text),
                _normalize_text(passed_text),
                n=5,
            )
            if sim > _MAX_DEDUP_SIMILARITY:
                is_duplicate = True
                logger.debug(f"   [Validation] 重复过滤: sim={sim:.4f} > {_MAX_DEDUP_SIMILARITY}, chunk[:50]={chunk_text[:50]!r}")
                rejected.append({**chunk, "layer1_reason": f"重复：与已有 chunk 相似度 {sim:.2f} > {_MAX_DEDUP_SIMILARITY}", "layer1_score": sim})
                break
        if is_duplicate:
            continue

        # 4. N-gram + 编辑距离规则校验（保留原有规则）
        if source_type == "pdf":
            source_text = pdf_full_text
        elif source_type == "web":
            url = chunk.get("source_url", "")
            source_text = web_full_texts.get(url, "")
            if not source_text:
                source_text = chunk.get("source_snippet", "") or chunk_text
        else:
            source_text = chunk_text

        is_distorted, score, reason = _is_distorted(chunk_text, source_text)
        if is_distorted:
            logger.debug(f"   [Validation] 失真过滤: score={score:.4f}, reason={reason}, chunk[:50]={chunk_text[:50]!r}")
            rejected.append({**chunk, "layer1_reason": f"失真: {reason}", "layer1_score": score})
            continue

        # 通过 Layer 1
        chunk_copy = dict(chunk)
        chunk_copy["layer1_score"] = round(score, 4)
        candidates.append(chunk_copy)

    logger.info(f"   [Validation] Layer 1 粗筛完成: {len(candidates)} 候选, {len(rejected)} 过滤")
    return candidates, rejected


# ============================================================
#  节点入口
# ============================================================

def chunk_validation_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Chunk 校验节点（仅 Layer 1 规则粗筛，已移除 Layer 2 LLM 校验）。

    输入：
      - top_k_chunks: 检索结果（含 PDF + Web 切片）
      - cleaned_chunks: PDF 原始切片（用于比对）
      - pdf_parsed_chunks: 缓存的 PDF 解析块

    输出：
      - source_materials: 通过校验的素材（只读，不可修改）
      - material_pool_frozen: True
      - validation_stats: 校验统计信息
    """
    top_k_chunks = state.get("top_k_chunks", [])
    cleaned_chunks = state.get("cleaned_chunks", [])
    pdf_parsed_chunks = state.get("pdf_parsed_chunks", [])
    task = state.get("task", "")
    sub_tasks = state.get("sub_tasks", [])

    logger.info(f"✅ [Validation] 开始 Chunk 校验（Layer 1 规则粗筛）...")
    logger.info(f"   [Validation] 待校验: {len(top_k_chunks)} 条")

    if not top_k_chunks:
        logger.warning("   [Validation] 无素材可校验，跳过")
        return {
            "source_materials": [],
            "material_pool_frozen": True,
            "validation_stats": {"total": 0, "passed": 0, "rejected": 0, "layer1_passed": 0},
        }

    # 构建来源原文映射
    pdf_full_text = ""
    pdf_source = pdf_parsed_chunks or cleaned_chunks
    if pdf_source:
        pdf_full_text = "\n".join([c.get("text", "") for c in pdf_source])

    web_full_texts = {}
    for item in top_k_chunks:
        if item.get("source_type") == "web":
            cft = item.get("cleaned_full_text", "")
            url = item.get("source_url", "")
            if cft:
                web_full_texts[url] = cft

    # Layer 1：无 LLM 快速粗筛
    layer1_start = time.time()
    candidates, layer1_rejected = _layer1_fast_filter(top_k_chunks, task, pdf_full_text, web_full_texts)
    layer1_elapsed = time.time() - layer1_start
    logger.info(f"   [Validation] Layer 1 耗时: {layer1_elapsed:.2f}s")

    # 构建 source_materials（candidates 即最终通过素材）
    source_materials = []
    for i, item in enumerate(candidates):
        source_materials.append({
            "text": item.get("text", ""),
            "source_index": item.get("source_index", i),
            "rerank_score": item.get("rerank_score", 0),
            "source_type": item.get("source_type", "unknown"),
            "trust_tier": item.get("trust_tier", "unverified"),
            "source_url": item.get("source_url", ""),
            "source_snippet": item.get("source_snippet", ""),
            "metadata": item.get("metadata", {}),
            "validation_score": item.get("layer1_score", 0.0),
            "validation_source": "layer1_only",
        })

    stats = {
        "total": len(top_k_chunks),
        "layer1_passed": len(candidates),
        "layer1_rejected": len(layer1_rejected),
        "passed": len(source_materials),
        "rejected": len(layer1_rejected),
        "layer1_rejected_details": layer1_rejected[:5],
    }

    # ===== 构建 validation_summary（用于二次检索判断） =====
    passed_count = len(source_materials)
    missing_sub_tasks = []
    if sub_tasks and passed_count < 2:
        # 统计哪些子任务方向素材不足
        sub_task_texts = []
        for st in sub_tasks:
            st_text = st.get("sub_query", st.get("task_text", st.get("text", "")))
            sub_task_texts.append(st_text)

        all_text = " ".join([m.get("text", "") for m in source_materials])
        for st_text in sub_task_texts:
            if not st_text:
                continue
            keywords = st_text[:20].strip()
            count = all_text.count(keywords) if keywords else 0
            if count < 2:
                missing_sub_tasks.append(st_text)

        # 如果全部缺失，只取前 2 个
        if len(missing_sub_tasks) > 2:
            missing_sub_tasks = missing_sub_tasks[:2]

    validation_summary = {
        "passed_count": passed_count,
        "total_count": len(top_k_chunks),
        "missing_sub_tasks": missing_sub_tasks,
        "needs_retrieval": passed_count < 2 and len(missing_sub_tasks) > 0,
    }

    logger.info(f"   [Validation] 校验完成: {stats['passed']} 通过, {stats['rejected']} 剔除 (Layer 1)")
    logger.info(f"   [Validation] 校验摘要: passed_count={passed_count}, missing={len(missing_sub_tasks)} 子主题")

    return {
        "source_materials": source_materials,
        "material_pool_frozen": True,
        "validation_stats": stats,
        "validation_summary": validation_summary,
    }

