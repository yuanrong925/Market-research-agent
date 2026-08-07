"""
第一阶段：数据摄入与清洗节点（Ingestion）

SOP 规范：
  1. 支持 PDF 文件解析（PyMuPDF/fitz）
  2. 文本清洗（去噪、去重、分段）
  3. 构建向量索引（ChromaDB）
"""

import hashlib
import json
import os
import re
from typing import Any

from core.utils.logger import get_logger
from business.market_research.state import AgentState

logger = get_logger(__name__)


# 缓存目录
_CACHE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".cache",
    "pdf_chunks",
)


# ============================================================
#  PDF 解析
# ============================================================

def _extract_text_from_pdf(file_path: str) -> str:
    """使用 PyMuPDF 提取 PDF 文本（带资源安全释放）"""
    import fitz
    doc = fitz.open(file_path)
    try:
        texts = []
        for page in doc:
            texts.append(page.get_text())
        return "\n".join(texts)
    finally:
        doc.close()


# ============================================================
#  文本清洗（增强版：去页眉页脚、合并断行、过滤乱码）
# ============================================================

# 常见页眉页脚模式（中文/英文）
_PAGE_HEADER_FOOTER_PATTERNS = [
    r'^\d+\s*$',                                          # 纯页码行
    r'^\d+\s*/\s*\d+\s*$',                                # "1 / 10" 页码
    r'^第\s*\d+\s*页\s*,?\s*共\s*\d+\s*页\s*$',          # "第 1 页，共 10 页"
    r'^第\s*\d+\s*页\s*$',                                 # "第 1 页"
    r'^\d+\s*of\s*\d+\s*$',                               # "1 of 10"
    r'^Page\s*\d+\s*of\s*\d+\s*$',                        # "Page 1 of 10"
    r'^Page\s*\d+\s*$',                                    # "Page 1"
    r'^-\s*\d+\s*-$',                                      # "- 1 -"
    r'^=\s*\d+\s*=$',                                      # "= 1 ="
    r'^【.*?】\s*$',                                       # 纯页眉标记行
    r'^www\.\S+\.\S+\s*$',                                # 纯网址行
    r'^Copyright\s.*$',                                    # Copyright 行
    r'^©\s.*$',                                            # © 行
    r'^All\s+Rights\s+Reserved.*$',                        # 版权声明
    r'^Confidential.*$',                                    # 机密标记
    # ---- v2 增强：新增模式 ----
    r'^目录\s*$',                                          # "目录" 单独一行
    r'^前言\s*$',                                          # "前言" 单独一行
    r'^摘要\s*$',                                          # "摘要" 单独一行
    r'^引言\s*$',                                          # "引言" 单独一行
    r'^参考文献\s*$',                                      # "参考文献" 单独一行
    r'^附录\s*$',                                          # "附录" 单独一行
    r'^[A-Z][a-z]+\s+\d{4}\s*$',                          # "January 2025" 日期页眉
    r'^\d{4}\s*年\s*\d{1,2}\s*月\s*$',                    # "2025年1月" 日期页眉
    r'^[A-Z][A-Z\s]+$',                                    # 全大写单词行（可能是页眉标题）
    r'^免责声明.*$',                                       # 免责声明
    r'^版权所有.*$',                                       # 版权所有
    r'^-\s*[A-Za-z0-9\s]+\s*-$',                          # "- 标题 -" 装饰行
]

# 乱码/不可见字符范围
_GARBLED_CHAR_PATTERN = re.compile(
    r'[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]'  # 控制字符
    r'|[\ufff0-\uffff]'                                          # Unicode 特殊区
    r'|[\u200b-\u200f\u2028-\u202f\u2060-\u206f]'                # 零宽字符/格式字符
    # ---- v2 增强：更多异常字符 ----
    r'|[\u2066-\u2069]'                                          # 双向文本控制符
    r'|[\u00ad]'                                                  # 软连字符
    r'|[\ufeff]'                                                  # BOM
)

# 常见乱码替换（PDF 提取常见错误）
_GARBLED_REPLACEMENTS = {
    '\uf0b7': '·',    # 项目符号
    '\uf0d8': '▼',
    '\uf0a7': '§',
    '\uf02d': '—',    # 破折号
    '\uf0ae': '→',
    '\uf020': ' ',    # 全角空格
    '\u3000': ' ',    # 全角空格
    # ---- v2 增强：更多替换 ----
    '\uf0fc': '·',    # 另一种项目符号
    '\uf0b0': '°',    # 度数符号
    '\uf0a8': '¨',    # 分音符
    '\uf0b8': '¸',    # 变音符号
    '\uf0a9': '©',    # 版权符号
    '\u2010': '-',    # 连字符
    '\u2011': '-',    # 不间断连字符
    '\u2012': '-',    # 短划线
    '\u2013': '-',    # 短破折号
    '\u2014': '—',    # 长破折号
    '\u2015': '—',    # 水平线
    '\u2018': "'",    # 左单引号
    '\u2019': "'",    # 右单引号
    '\u201c': '"',    # 左双引号
    '\u201d': '"',    # 右双引号
    '\u00a0': ' ',    # 不间断空格
}


def _is_header_footer_line(line: str) -> bool:
    """判断是否为页眉页脚行"""
    stripped = line.strip()
    if not stripped:
        return False
    for pattern in _PAGE_HEADER_FOOTER_PATTERNS:
        if re.match(pattern, stripped):
            return True
    # 短行（<8字符）且以数字为主 → 大概率页码
    if len(stripped) < 8 and re.match(r'^[\d\s\-=/\\|]+$', stripped):
        return True
    return False


def _merge_broken_lines(text: str) -> str:
    """
    合并因 PDF 换行断开的中文段落。
    规则：
      - 如果行尾不是句号/问号/感叹号/冒号/分号，且下一行不是空行，则合并
      - 如果行尾是英文连字符，去掉连字符并合并
    """
    lines = text.split('\n')
    merged = []
    buffer = ""

    for line in lines:
        stripped = line.rstrip()
        # 如果 buffer 非空且当前行是页眉页脚，跳过
        if _is_header_footer_line(stripped):
            continue
        # 如果 buffer 为空，直接开始新段落
        if not buffer:
            buffer = stripped
            continue
        # 判断是否应该合并
        if stripped and not re.match(r'^[\s\n\r]*$', stripped):
            # 行尾是连字符 → 去掉连字符合并
            if buffer.endswith('-') and not buffer.endswith('——'):
                buffer = buffer[:-1] + stripped
            # 行尾不是句尾标点 → 合并（中文段落换行）
            # 句尾结束标点集合
            end_punct = {"。", "！", "？", "」", "』", '"', "'", "）", "］", "》", "】"}
            if buffer[-1:] not in end_punct:
                buffer += stripped
            else:
                # 句尾结束，换行
                merged.append(buffer)
                buffer = stripped
        else:
            # 空行，结束当前段落
            if buffer:
                merged.append(buffer)
                buffer = ""
    if buffer:
        merged.append(buffer)

    return '\n'.join(merged)


def _clean_text(text: str) -> str:
    """
    清洗文本：去页眉页脚、合并断行、过滤乱码、去多余空白。

    增强版（v2）：
      1. 剔除页眉页脚行（页码、版权、网址等）
      2. 合并因 PDF 换行断开的中文段落
      3. 替换/移除乱码字符
      4. 压缩多余空白
    """
    # 1. 替换已知乱码字符
    for garbled, replacement in _GARBLED_REPLACEMENTS.items():
        text = text.replace(garbled, replacement)

    # 2. 移除不可见/控制字符
    text = _GARBLED_CHAR_PATTERN.sub('', text)

    # 3. 规范化换行（统一 \r\n → \n）
    text = text.replace('\r\n', '\n').replace('\r', '\n')

    # 4. 合并因 PDF 换行断开的中文段落
    text = _merge_broken_lines(text)

    # 5. 压缩多余空白
    text = re.sub(r'[ \t]+', ' ', text)       # 多空格 → 单空格
    text = re.sub(r'\n{3,}', '\n\n', text)    # 多空行 → 最多2个

    # 6. 去除首尾空白
    text = text.strip()

    return text


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[dict[str, Any]]:
    """将文本分块（修复：避免重复包含重叠区域导致的重复 chunk）"""
    if overlap >= chunk_size:
        overlap = chunk_size // 4  # 保证 overlap 不会吃掉前进量

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
                "source_type": "pdf",
            })
        # 前进时保证至少前进 chunk_size - overlap 长度，避免死循环
        advance = max(end - overlap, start + 1) if end < len(text) else len(text)
        if advance <= start:
            advance = start + 1  # 强制前进至少 1 字符
        start = advance
    return chunks


# ============================================================
#  磁盘缓存
# ============================================================

def _compute_fingerprint(pdf_path: str) -> str:
    """计算 PDF 文件指纹，用于缓存键"""
    if not pdf_path or not os.path.exists(pdf_path):
        return ""
    try:
        h = hashlib.md5()
        with open(pdf_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def _try_load_from_cache(fingerprint: str) -> list[dict[str, Any]] | None:
    """尝试从磁盘缓存加载清洗后的块"""
    if not fingerprint:
        return None
    os.makedirs(_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(_CACHE_DIR, f"{fingerprint}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if cached and len(cached) > 0:
                logger.info(f"📦 [Ingestion] 从磁盘缓存加载 {len(cached)} 个清洗块")
                return cached
        except Exception:
            pass
    return None


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


# ============================================================
#  构建 Chroma 集合（修复：UUID 集合名，避免哈希碰撞）
# ============================================================

def _cleanup_old_chroma_collections(client: Any, current_name: str, max_keep: int = 5):
    """清理旧的 Chroma 集合，避免 chroma_db 目录无限增长
    策略：
      - 只删除名称以 'pdf-' 开头的集合
      - 保留最近 max_keep 个集合（按名称字典序，旧集合排在前面）
      - 保留当前正在使用的集合
    """
    try:
        all_collections = client.list_collections()
        pdf_collections = [
            c for c in all_collections
            if c.name.startswith("pdf-") and c.name != current_name
        ]
        if len(pdf_collections) <= max_keep:
            return

        # 按名称排序（UUID 开头按创建时间大致有序），删除最旧的
        pdf_collections.sort(key=lambda c: c.name)
        to_delete = pdf_collections[:-max_keep]
        for c in to_delete:
            try:
                client.delete_collection(c.name)
                logger.info(f"   🧹 清理旧 Chroma 集合: {c.name}")
            except Exception:
                pass
        logger.info(f"   🧹 清理完成: 删除 {len(to_delete)} 个旧集合，保留 {max_keep} 个")
    except Exception:
        pass


def _compute_content_hash(texts: list[str]) -> str:
    """计算文本内容的哈希值，用于 Chroma 集合名称"""
    combined = "".join(texts)
    return hashlib.md5(combined.encode()).hexdigest()[:16]


def _build_pdf_collection(texts: list[str], metadatas: list[dict], model_mode: str) -> Any:
    """构建 PDF 向量集合

    修复：
      1. 使用内容哈希作为集合名称，相同 PDF 复用同一集合，避免 chroma_db 目录无限增长
      2. 降级时明确记录原因
      3. 定期清理旧集合
    """
    from core.retrieval.chroma import create_chroma_client, DashScopeEmbeddingFunction
    from core.retrieval.hybrid import HybridRetriever
    from core.config import get_config

    cfg = get_config()

    # 检查 Embedding API Key 是否配置，提前给出明确提示
    if not cfg.dashscope_api_key:
        logger.warning("DASHSCOPE_API_KEY 未配置，直接降级到 inmemory 模式（仅 BM25 检索）")
        hybrid = HybridRetriever()
        hybrid.build_index(texts, metadatas)
        return {
            "type": "inmemory",
            "texts": texts,
            "metadatas": metadatas,
            "fallback": True,
            "fallback_reason": "DASHSCOPE_API_KEY 未配置，Chroma 向量检索不可用，降级到 BM25 关键词检索",
            "hybrid": hybrid,
        }

    try:
        client = create_chroma_client()

        # 用内容哈希做集合名：相同 PDF 内容 → 复用同一集合，避免无限增长
        content_hash = _compute_content_hash(texts)
        collection_name = f"pdf-{content_hash}"

        embedding_fn = DashScopeEmbeddingFunction(
            api_key=cfg.dashscope_api_key,
            model_name=cfg.embedding_model,
            api_base=cfg.embedding_base_url,
        )

        # 先尝试获取已有集合
        collection = None
        try:
            collection = client.get_collection(
                name=collection_name,
                embedding_function=embedding_fn,
            )
            logger.info(f"   📦 复用已有 Chroma 集合: {collection_name}, docs={collection.count()}")
        except Exception:
            pass

        if collection is None:
            # 创建新集合
            collection = client.create_collection(
                name=collection_name,
                embedding_function=embedding_fn,
            )
            # 批量添加文本
            collection.add(
                ids=[f"doc-{i}" for i in range(len(texts))],
                documents=texts,
                metadatas=metadatas,
            )
            logger.info(f"   ✅ Chroma 集合新建成功: {collection_name}, docs={collection.count()}")

        # 清理旧集合（仅保留最近 5 个无关的 pdf-* 集合）
        _cleanup_old_chroma_collections(client, collection_name, max_keep=5)

        hybrid = HybridRetriever(chroma_collection=collection)
        hybrid.build_index(texts, metadatas, chroma_collection=collection)

        return {"type": "chroma", "collection": collection, "hybrid": hybrid, "collection_name": collection_name}

    except Exception as exc:
        reason = str(exc)
        logger.warning(f"Chroma 构建失败，降级到内存模式: {reason}")
        hybrid = HybridRetriever()
        hybrid.build_index(texts, metadatas)
        return {
            "type": "inmemory",
            "texts": texts,
            "metadatas": metadatas,
            "fallback": True,
            "fallback_reason": f"Chroma 构建失败: {reason}，降级到 BM25 关键词检索",
            "hybrid": hybrid,
        }


def data_ingestion_node(state: AgentState):
    """数据摄入节点（SOP 第一阶段）"""
    task = state.get("task", "")
    pdf_collection = state.get("pdf_collection")
    model_mode = state.get("model_mode", "cloud")

    logger.info(f"📄 [Ingestion] 开始数据摄入...")

    # ============================================================
    #  模式拦截：纯联网模式完全忽略 PDF，不解析不检索
    # ============================================================
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    if manual_mode in ("enabled", "web_only"):
        logger.info(f"   [Ingestion] 纯联网模式，跳过 PDF 解析，完全忽略上传文档")
        return {"cleaned_chunks": []}

    # ============================================================
    #  【新增】状态级缓存：检查 pdf_parsed_chunks，避免子任务重复解析
    # ============================================================
    pdf_parsed_chunks = state.get("pdf_parsed_chunks")
    if pdf_parsed_chunks is not None:
        logger.info(f"   [Ingestion] 命中状态缓存: {len(pdf_parsed_chunks)} 个解析块，跳过完整解析")
        if pdf_collection is not None:
            return {"cleaned_chunks": pdf_parsed_chunks, "pdf_parsed_chunks": pdf_parsed_chunks}
        # 有缓存块但无集合，需重建
        texts = [c["text"] for c in pdf_parsed_chunks]
        metadatas = [{"source": "PDF", "page": c.get("source_index", 0)} for c in pdf_parsed_chunks]
        collection = _build_pdf_collection(texts, metadatas, model_mode)
        return {
            "cleaned_chunks": pdf_parsed_chunks,
            "pdf_collection": collection,
            "pdf_parsed_chunks": pdf_parsed_chunks,
        }

    # 如果已有 pdf_collection 但无 pdf_parsed_chunks，补全缓存
    if pdf_collection is not None:
        logger.info(f"   [Ingestion] 已有 PDF 集合，跳过解析")
        cleaned_chunks = state.get("cleaned_chunks", [])
        return {"cleaned_chunks": cleaned_chunks, "pdf_parsed_chunks": cleaned_chunks}

    # 从文件路径解析 PDF
    pdf_path = state.get("pdf_path", "")
    if not pdf_path:
        logger.warning(f"   [Ingestion] 无 PDF 文件路径，跳过")
        return {"cleaned_chunks": []}

    try:
        # ---- 尝试磁盘缓存 ----
        fingerprint = _compute_fingerprint(pdf_path)
        cached = _try_load_from_cache(fingerprint)
        if cached is not None:
            chunks = cached
            # 缓存命中，但需要重新构建集合
            texts = [c["text"] for c in chunks]
            metadatas = [{"source": "PDF", "page": c.get("source_index", 0)} for c in chunks]
            collection = _build_pdf_collection(texts, metadatas, model_mode)
            logger.info(f"   ✅ 缓存命中，数据摄入完成: {len(chunks)} 个文本块")
            return {
                "cleaned_chunks": chunks,
                "pdf_collection": collection,
                "pdf_parsed_chunks": chunks,
            }

        # ---- 缓存未命中，完整解析 ----
        raw_text = _extract_text_from_pdf(pdf_path)
        cleaned = _clean_text(raw_text)
        chunks = _chunk_text(cleaned)

        texts = [c["text"] for c in chunks]
        metadatas = [{"source": "PDF", "page": c.get("source_index", 0)} for c in chunks]

        collection = _build_pdf_collection(texts, metadatas, model_mode)

        # 写入磁盘缓存
        _save_to_cache(fingerprint, chunks)

        logger.info(f"   ✅ 数据摄入完成: {len(chunks)} 个文本块")

        return {
            "cleaned_chunks": chunks,
            "pdf_collection": collection,
            "pdf_parsed_chunks": chunks,
        }

    except Exception as e:
        logger.error(f"   ❌ 数据摄入失败: {e}")
        return {
            "cleaned_chunks": [],
            "error_message": f"PDF 解析失败: {str(e)}",
        }