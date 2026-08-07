"""
证据锚点匹配引擎 — 多级语义匹配策略

v2 改进：
  1. 保留原有精确子串匹配（策略A/B/C/D）
  2. 新增策略E：关键实体提取 + 实体匹配（数值、百分比、年份、专有名词）
  3. 新增策略F：语义池匹配（复用 ChromaDB embedding 做语义相似度）
  4. 新增策略G：LLM 语义判断题（最高精度，仅对前几轮未匹配的句子使用）
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
#  全局缓存：避免重复加载 embedding 模型
# ============================================================
_embedding_model = None
_embedding_cache: Dict[str, List[float]] = {}
# 素材句子 embedding 缓存：key = materials_text 的前 200 字符，value = [(sentence, emb), ...]
_materials_embedding_cache: Dict[str, List[Tuple[str, List[float]]]] = {}


def _get_embedding(text: str) -> List[float]:
    """获取文本的 embedding 向量（使用 ChromaDB 的 embedding 函数）"""
    global _embedding_model
    if _embedding_model is None:
        try:
            from chromadb.utils import embedding_functions
            _embedding_model = embedding_functions.DefaultEmbeddingFunction()
        except ImportError:
            logger.warning("   ⚠️ chromadb 不可用，回退到文本匹配")
            return []
        except Exception as e:
            logger.warning(f"   ⚠️ 加载 embedding 模型失败: {e}")
            return []

    cache_key = text[:200]  # 用前 200 字符做缓存键
    if cache_key in _embedding_cache:
        return _embedding_cache[cache_key]

    try:
        emb = _embedding_model([text[:512]])  # 截断到 512 字符
        if emb and len(emb) > 0:
            # emb[0] 可能是 numpy array，转成 Python list 避免后续布尔判断异常
            result = emb[0].tolist() if hasattr(emb[0], 'tolist') else list(emb[0])
            _embedding_cache[cache_key] = result
            return result
    except Exception as e:
        logger.warning(f"   ⚠️ embedding 计算失败: {e}")

    return []


def _get_materials_embeddings(materials_text: str) -> List[Tuple[str, List[float]]]:
    """
    预计算并缓存 research_materials 中所有句子的 embedding。
    避免在策略 F 中为每个待核查句子重复计算素材句子的 embedding。
    """
    cache_key = materials_text[:200]
    if cache_key in _materials_embedding_cache:
        return _materials_embedding_cache[cache_key]

    # 按句号/换行分句
    sentences = re.split(r'[。\n]', materials_text)
    result = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) < 10:
            continue
        emb = _get_embedding(sent)
        if emb and len(emb) > 0:
            result.append((sent, emb))

    _materials_embedding_cache[cache_key] = result
    logger.info(f"   📦 [缓存] 素材句子 embedding 已预计算: {len(result)} 句")
    return result


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """计算余弦相似度"""
    # 确保是 Python list（防止 numpy array 导致布尔判断异常）
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) == 0 or len(b) == 0 or len(a) != len(b):
            return 0.0
    else:
        return 0.0
    try:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)
    except Exception:
        return 0.0


# ============================================================
#  关键实体提取
# ============================================================

_NUM_PATTERN = re.compile(r'[-+]?\d+\.?\d*[万亿千百十万]?')
_PERCENT_PATTERN = re.compile(r'\d+\.?\d*%')
_YEAR_PATTERN = re.compile(r'(?:19|20)\d{2}年?')
_QUOTE_PATTERN = re.compile(r'[""「」『』]([^""「」『』]{3,50})[""「」『』]')


def extract_key_entities(text: str) -> List[str]:
    """从文本中提取关键实体：数值、百分比、年份、引号内容、专有名词"""
    entities = []

    # 数值
    for m in _NUM_PATTERN.finditer(text):
        entities.append(m.group())

    # 百分比
    for m in _PERCENT_PATTERN.finditer(text):
        entities.append(m.group())

    # 年份
    for m in _YEAR_PATTERN.finditer(text):
        entities.append(m.group())

    # 引号内容
    for m in _QUOTE_PATTERN.finditer(text):
        entities.append(m.group(1))

    # 去重
    return list(set(entities))


# ============================================================
#  主匹配函数
# ============================================================

def find_evidence_anchor(sentence: str, research_materials: str, text_only: bool = False) -> str:
    """
    在 research_materials 中查找 sentence 的原文锚点。

    多级匹配策略（按优先级降序）：
    A. 精确子串匹配（含标点）
    B. 去标点后匹配
    C. 关键词片段分段匹配（至少2段命中）
    D. 前20字符模糊匹配
    E. 关键实体匹配（提取数值/百分比/年份，定位到素材中包含这些实体的句子）
    F. 语义池匹配（使用缓存素材 embedding，阈值 0.85+）
    G. LLM 语义判断（仅对前几轮未匹配的句子使用，由外部调用）

    参数：
    - text_only: True 时跳过策略 F（语义匹配），用于超时降级场景

    返回：
    - 匹配到的素材片段（含上下文）
    - 空字符串表示未找到
    """
    if not sentence or not research_materials:
        return ""

    clean = sentence.strip().strip('"').strip("'").strip("「」『』")
    if len(clean) < 5:
        return ""

    # ====== 策略A：精确子串 ======
    if clean in research_materials:
        return _extract_context(research_materials, clean)

    # ====== 策略B：去标点匹配 ======
    punct_pattern = re.compile(r'[，。！？、；：""\'\'（）【】\[\]{}《》\s]')
    clean_no_punct = punct_pattern.sub('', clean)
    research_no_punct = punct_pattern.sub('', research_materials)
    if len(clean_no_punct) >= 5 and clean_no_punct in research_no_punct:
        idx = research_no_punct.find(clean_no_punct)
        start = max(0, idx - 20)
        end = min(len(research_materials), idx + len(clean_no_punct) + 20)
        return research_materials[start:end]

    # ====== 策略C：关键词片段分段匹配 ======
    segments = _extract_key_segments(clean, min_len=5)
    matched = [s for s in segments if s in research_materials]
    if len(matched) >= 2:
        return _extract_context(research_materials, matched[0])

    # ====== 策略D：前20字符 ======
    short_key = clean[:20].strip()
    if len(short_key) >= 6 and short_key in research_materials:
        return _extract_context(research_materials, short_key)

    # ====== 策略E：关键实体匹配 ======
    entities = extract_key_entities(clean)
    if entities:
        entities.sort(key=len, reverse=True)
        for entity in entities:
            if len(entity) >= 3 and entity in research_materials:
                ctx = _extract_context(research_materials, entity)
                surrounding = _extract_surrounding_sentence(research_materials, entity)
                if surrounding:
                    return f"【实体匹配】{entity} | 上下文: {surrounding}"
                return ctx

    # ====== 策略F：语义池匹配（使用缓存素材 embedding） ======
    if text_only:
        # 降级模式：跳过语义匹配策略
        return ""

    try:
        sentence_emb = _get_embedding(clean)
        if sentence_emb and len(sentence_emb) > 0:
            materials_embeddings = _get_materials_embeddings(research_materials)
            best_score = 0.0
            best_sent = ""
            for sent, sent_emb in materials_embeddings:
                score = _cosine_similarity(sentence_emb, sent_emb)
                if score > best_score:
                    best_score = score
                    best_sent = sent

            if best_score >= 0.85 and best_sent:
                logger.info(f"   🔗 [语义锚点] 相似度={best_score:.3f} | 句: {best_sent[:50]}...")
                return _extract_context(research_materials, best_sent[:30])
    except Exception as e:
        logger.warning(f"   ⚠️ 语义匹配异常: {e}")

    return ""


def _extract_surrounding_sentence(text: str, keyword: str) -> str:
    """在 text 中找到包含 keyword 的完整句子"""
    idx = text.find(keyword)
    if idx == -1:
        return ""

    # 找到句子开头
    sent_start = max(
        text.rfind("。", 0, idx),
        text.rfind("\n", 0, idx),
        text.rfind("！", 0, idx),
        text.rfind("？", 0, idx),
    )
    if sent_start == -1:
        sent_start = max(0, idx - 80)
    else:
        sent_start += 1

    # 找到句子结尾
    sent_end = min(
        text.find("。", idx),
        text.find("\n", idx),
        text.find("！", idx),
        text.find("？", idx),
    )
    if sent_end == -1:
        sent_end = min(len(text), idx + len(keyword) + 80)

    return text[sent_start:sent_end].strip()


# ============================================================
#  语义匹配批量接口（用于核查器前置校验）
# ============================================================

def batch_semantic_check(
    sentences: List[str],
    research_materials: str,
    threshold: float = 0.85,
) -> List[Dict[str, Any]]:
    """
    批量语义检查：对一组句子，逐一检查是否在素材中找到语义匹配。
    用于核查器前置校验，提前过滤掉"改写但意思一致"的句子。

    返回：
    [
        {
            "sentence": "...",
            "matched": True/False,
            "anchor": "匹配到的素材片段",
            "similarity": 0.92,
            "match_method": "exact|entity|semantic"
        },
        ...
    ]
    """
    results = []
    for sent in sentences:
        anchor = find_evidence_anchor(sent, research_materials)
        if anchor:
            # 判断匹配方法
            method = "exact"
            if anchor.startswith("【实体匹配】"):
                method = "entity"
            elif "相似度" in anchor or "语义锚点" in anchor:
                method = "semantic"

            results.append({
                "sentence": sent,
                "matched": True,
                "anchor": anchor,
                "similarity": 1.0 if method == "exact" else 0.9,
                "match_method": method,
            })
        else:
            results.append({
                "sentence": sent,
                "matched": False,
                "anchor": "",
                "similarity": 0.0,
                "match_method": "none",
            })

    return results


# ============================================================
#  原有函数（保留向后兼容）
# ============================================================

def extract_key_segments(text: str, min_len: int = 5) -> List[str]:
    """提取文本中的有意义片段（按标点拆分）"""
    parts = re.split(r'[，。！？、；：,.!?;:\s]+', text)
    segments = [p.strip() for p in parts if len(p.strip()) >= min_len]
    if len(segments) < 2 and len(text) > min_len * 2:
        mid = len(text) // 2
        segments = [text[:mid], text[mid:]]
    return segments


def extract_context(text: str, keyword: str, window: int = 100) -> str:
    """在 text 中定位 keyword，返回前后 window 字符的上下文"""
    idx = text.find(keyword)
    if idx == -1:
        return keyword[:200]
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    ctx = text[start:end]
    if start > 0:
        ctx = "..." + ctx
    if end < len(text):
        ctx = ctx + "..."
    return ctx


def chunk_report(report: str, max_chars: int, max_chunks: int) -> List[str]:
    """将报告分块"""
    chunks = []
    remaining = report
    for _ in range(max_chunks):
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
        if not remaining.strip():
            break
    if remaining.strip() and len(chunks) == max_chunks:
        logger.warning("   ⚠️ 报告过长，尾部已跳过")
    return chunks


# 保留旧函数名别名（兼容引用）
_extract_key_segments = extract_key_segments
_extract_context = extract_context
