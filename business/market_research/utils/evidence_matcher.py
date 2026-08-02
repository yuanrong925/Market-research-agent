"""证据锚点匹配引擎 — 在素材中查找原文支撑"""

import re
from typing import List
from core.utils.logger import get_logger

logger = get_logger(__name__)


def find_evidence_anchor(sentence: str, research_materials: str) -> str:
    """
    在 research_materials 中查找 sentence 的原文锚点。

    多级匹配策略：
    A. 精确子串匹配（含标点）
    B. 去标点后匹配
    C. 关键词片段分段匹配（至少2段命中）
    D. 前20字符模糊匹配
    """
    if not sentence or not research_materials:
        return ""

    clean = sentence.strip().strip('"').strip("'").strip("「」『』")
    if len(clean) < 5:
        return ""

    # 策略A：精确子串
    if clean in research_materials:
        return extract_context(research_materials, clean)

    # 策略B：去标点匹配
    punct_pattern = re.compile(r'[，。！？、；：""\'\'（）【】\[\]{}《》\s]')
    clean_no_punct = punct_pattern.sub('', clean)
    research_no_punct = punct_pattern.sub('', research_materials)
    if len(clean_no_punct) >= 5 and clean_no_punct in research_no_punct:
        idx = research_no_punct.find(clean_no_punct)
        start = max(0, idx - 20)
        end = min(len(research_materials), idx + len(clean_no_punct) + 20)
        return research_materials[start:end]

    # 策略C：关键词片段分段匹配
    segments = extract_key_segments(clean, min_len=5)
    matched = [s for s in segments if s in research_materials]
    if len(matched) >= 2:
        return extract_context(research_materials, matched[0])

    # 策略D：前20字符
    short_key = clean[:20].strip()
    if len(short_key) >= 6 and short_key in research_materials:
        return extract_context(research_materials, short_key)

    return ""


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