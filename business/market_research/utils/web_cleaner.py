"""
网页原始内容清洗工具

功能：
  1. 接收网页 URL，抓取原始 HTML
  2. 清洗：过滤广告、导航栏、页脚、无关冗余文本、重复段落
  3. 保留正文原文，不做任何 LLM 概括或改写
  4. 分段切片，返回清洗后的正文切片列表

严格遵守：
  - 禁止调用 LLM 进行概括、改写
  - 只做规则/启发式清洗 + 统计去重
  - 输出是"原始正文切片"，不是"摘要"
"""

import hashlib
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

from core.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
#  配置常量
# ============================================================

# 默认请求超时（秒）
_REQUEST_TIMEOUT = 15

# 请求头（模拟浏览器）
_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 正文内容最小长度阈值（字符）
_MIN_PARAGRAPH_LENGTH = 20

# 段落重复率阈值（去重用）
_DUPLICATE_SIMILARITY_THRESHOLD = 0.85

# 切片大小（字符）
_CHUNK_SIZE = 500
_CHUNK_OVERLAP = 50

# 常见广告/导航/页脚 CSS 选择器（中英文）
_AD_SELECTORS = [
    "div.ad", "div.ads", "div.advertisement", "div.advert",
    "div.banner", "div.banner-ad", "div.promotion",
    "aside", "nav", "footer",
    "div.sidebar", "div.widget", "div.comment",
    "div.footer", "div.header", "div.nav", "div.navigation",
    "div.share", "div.share-bar", "div.social",
    "div.recommend", "div.related", "div.recommendation",
    ".ad", ".ads", ".advertisement", ".advert",
    ".banner", ".banner-ad", ".promotion",
    "aside", "nav", "footer",
    ".sidebar", ".widget", ".comment",
    ".footer", ".header", ".nav", ".navigation",
    ".share", ".share-bar", ".social",
    ".recommend", ".related", ".recommendation",
    "div[class*='ad']", "div[id*='ad']",
    "div[class*='banner']", "div[id*='banner']",
    "div[class*='footer']", "div[class*='header']",
]

# 常见广告/导航关键词（用于文本识别）
_AD_KEYWORDS = [
    "广告", "推广", "赞助", "广告位", "ad", "ads", "sponsored",
    "navigation", "nav", "footer", "header", "sidebar",
    "推荐阅读", "相关文章", "热点新闻", "热门推荐",
    "分享到", "关注我们", "扫码", "二维码",
    "copyright", "©", "All Rights Reserved",
    "订阅", "注册", "登录", "用户评论",
    "你可能感兴趣", "猜你喜欢", "延伸阅读",
    "上一篇", "下一篇", "返回顶部",
    "关键词", "标签", "tag", "tags",
    "评论", "评论区", "回复",
]


# ============================================================
#  Step 1: 抓取网页原始 HTML
# ============================================================

def fetch_webpage_html(url: str) -> Optional[str]:
    """
    抓取网页原始 HTML。

    Args:
        url: 网页 URL

    Returns:
        原始 HTML 字符串，失败返回 None
    """
    try:
        logger.info(f"   🌐 [WebCleaner] 抓取: {url[:80]}...")
        resp = requests.get(
            url,
            headers=_DEFAULT_HEADERS,
            timeout=_REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        resp.raise_for_status()

        # 尝试从响应头或 HTML meta 检测编码
        encoding = resp.encoding or resp.apparent_encoding or "utf-8"
        resp.encoding = encoding

        html = resp.text
        logger.info(f"   ✅ [WebCleaner] 抓取成功: {len(html)} 字符, 编码={encoding}")
        return html

    except requests.exceptions.Timeout:
        logger.warning(f"   ⚠️ [WebCleaner] 抓取超时: {url[:60]}...")
        return None
    except requests.exceptions.RequestException as e:
        logger.warning(f"   ⚠️ [WebCleaner] 抓取失败: {e}")
        return None
    except Exception as e:
        logger.warning(f"   ⚠️ [WebCleaner] 未知异常: {e}")
        return None


# ============================================================
#  Step 2: 清洗 HTML — 去广告/导航/页脚
# ============================================================

def _remove_ad_elements(soup: BeautifulSoup) -> BeautifulSoup:
    """移除广告、导航、页脚等元素"""
    for selector in _AD_SELECTORS:
        try:
            for element in soup.select(selector):
                element.decompose()
        except Exception:
            pass
    return soup


def _is_ad_text(text: str) -> bool:
    """判断文本是否属于广告/导航类"""
    text_lower = text.lower().strip()
    if len(text_lower) < 5:
        return False
    for kw in _AD_KEYWORDS:
        if kw in text_lower:
            return True
    return False


def _filter_paragraphs(paragraphs: List[str]) -> List[str]:
    """过滤广告/导航段落"""
    filtered = []
    for p in paragraphs:
        if len(p) < _MIN_PARAGRAPH_LENGTH:
            continue
        if _is_ad_text(p):
            continue
        filtered.append(p)
    return filtered


def _deduplicate_paragraphs(paragraphs: List[str]) -> List[str]:
    """
    去重：移除重复或高度相似的段落。

    使用简单 N-gram 重叠比率判断相似度。
    """
    if len(paragraphs) <= 1:
        return paragraphs

    def _ngram_overlap(a: str, b: str, n: int = 5) -> float:
        """计算两个字符串的 n-gram 重叠比率"""
        a_grams = set(a[i:i+n] for i in range(len(a)-n+1))
        b_grams = set(b[i:i+n] for i in range(len(b)-n+1))
        if not a_grams or not b_grams:
            return 0.0
        intersection = a_grams & b_grams
        return len(intersection) / max(len(a_grams), len(b_grams))

    unique = []
    for p in paragraphs:
        is_dup = False
        for existing in unique:
            if _ngram_overlap(p, existing) > _DUPLICATE_SIMILARITY_THRESHOLD:
                is_dup = True
                break
        if not is_dup:
            unique.append(p)

    return unique


def _clean_whitespace(text: str) -> str:
    """清洗多余空白字符"""
    # 替换多个空白为单个空格
    text = re.sub(r'\s+', ' ', text)
    # 去掉行首行尾空白
    text = text.strip()
    return text


def _extract_body_text(html: str) -> str:
    """
    从 HTML 中提取正文文本。

    流程：
      1. 解析 HTML
      2. 移除广告/导航/页脚等元素
      3. 提取所有段落文本
      4. 过滤广告段落
      5. 去重
      6. 拼接为正文

    Returns:
        清洗后的正文文本（纯文本，不含 HTML）
    """
    soup = BeautifulSoup(html, "html.parser")

    # 移除广告元素
    soup = _remove_ad_elements(soup)

    # 尝试提取正文区域（优先 article / main 标签）
    body = soup.find("article") or soup.find("main") or soup.find("body") or soup

    # 提取所有段落（p 标签 + 直接文本块）
    paragraphs = []

    # 提取 p 标签
    for p in body.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            paragraphs.append(text)

    # 如果 p 标签太少，尝试提取所有 div 文本块
    if len(paragraphs) < 3:
        for div in body.find_all(["div", "section", "span"], recursive=True):
            text = div.get_text(strip=True)
            if text and len(text) > _MIN_PARAGRAPH_LENGTH * 2:
                # 避免重复添加（子节点已包含）
                if not any(text in existing for existing in paragraphs):
                    paragraphs.append(text)

    # 过滤广告段落
    paragraphs = _filter_paragraphs(paragraphs)

    # 去重
    paragraphs = _deduplicate_paragraphs(paragraphs)

    # 拼接
    body_text = "\n\n".join(paragraphs)
    body_text = _clean_whitespace(body_text)

    logger.info(
        f"   [WebCleaner] 清洗完成: "
        f"{len(paragraphs)} 段落, {len(body_text)} 字符"
    )
    return body_text


# ============================================================
#  Step 3: 切片
# ============================================================

def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    """将文本分块"""
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            # 优先在换行处断开
            newline_pos = text.rfind('\n', start, end)
            if newline_pos > start:
                end = newline_pos
        chunk_text = text[start:end].strip()
        if chunk_text:
            chunks.append({
                "text": chunk_text,
                "source_index": len(chunks),
                "source_type": "web",
            })
        advance = max(end - overlap, start + 1) if end < len(text) else len(text)
        if advance <= start:
            advance = start + 1
        start = advance

    return chunks


# ============================================================
#  主入口
# ============================================================

def clean_webpage(url: str, text_fallback: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    清洗网页并返回切片。

    Args:
        url: 网页 URL
        text_fallback: 如果抓取失败，是否使用已有的文本片段作为降级
            （例如 Tavily 返回的 snippet）

    Returns:
        清洗后的切片列表，每个元素包含 text / source_index / source_type
    """
    # 抓取 HTML
    html = fetch_webpage_html(url)

    if html is None:
        # 抓取失败，使用降级文本
        if text_fallback and len(text_fallback) > 50:
            logger.info(f"   [WebCleaner] 抓取失败，使用降级文本 ({len(text_fallback)} 字符)")
            cleaned = _clean_whitespace(text_fallback)
            chunks = _chunk_text(cleaned)
            for c in chunks:
                c["source_url"] = url
                c["fetch_status"] = "fallback"
            return chunks
        return []

    # 提取正文
    body_text = _extract_body_text(html)

    if not body_text or len(body_text) < 50:
        logger.warning(f"   ⚠️ [WebCleaner] 清洗后正文过短，使用降级文本")
        if text_fallback and len(text_fallback) > 50:
            cleaned = _clean_whitespace(text_fallback)
            chunks = _chunk_text(cleaned)
            for c in chunks:
                c["source_url"] = url
                c["fetch_status"] = "fallback"
            return chunks
        return []

    # 切片
    chunks = _chunk_text(body_text)
    for c in chunks:
        c["source_url"] = url
        c["fetch_status"] = "full_html"

    logger.info(f"   ✅ [WebCleaner] 网页清洗完成: {len(chunks)} 个切片 (来源: {url[:50]}...)")
    return chunks


def clean_webpages_batch(
    web_results: List[Dict[str, Any]],
    max_pages: int = 5,
) -> List[Dict[str, Any]]:
    """
    批量清洗网页。

    Args:
        web_results: 联网搜索结果列表，每个元素至少包含 url 和可选的 snippet
        max_pages: 最多清洗的页面数

    Returns:
        所有清洗后的切片合并列表
    """
    all_chunks = []

    for i, result in enumerate(web_results):
        if i >= max_pages:
            break

        url = result.get("source_url", "") or result.get("url", "")
        snippet = result.get("text", "") or result.get("snippet", "")

        if not url:
            continue

        chunks = clean_webpage(url, text_fallback=snippet)
        all_chunks.extend(chunks)

    logger.info(f"   [WebCleaner] 批量清洗: {len(web_results)} URL → {len(all_chunks)} 个切片")
    return all_chunks