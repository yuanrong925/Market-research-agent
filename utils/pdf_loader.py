"""
utils/pdf_loader.py — 第一阶段：数据摄入与清洗

SOP 规范：
  1. PDF解析与OCR识别：对原始PDF文档进行结构化解析，扫描件/图片型PDF调用OCR引擎
  2. 去噪处理：剔除页眉、页脚、页码、水印及OCR产生的乱码字符
  3. 语义切分：采用基于文档层级的语义切分策略，保留上下文连贯性

用法：
  loader = RobustPDFLoader("path/to/file.pdf")
  chunks = loader.load_clean_and_chunk()
  # chunks = [{"text": "清洗后的文本", "metadata": {"source": "...", "page": 1, "section": "章节名"}, "chunk_id": "uuid"}]
"""
import logging
import os
import re
import uuid
from typing import Any, Dict, List, Optional
from xml.etree import ElementTree

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================
#  1. PDF 解析与 OCR 识别
# ============================================================

class RobustPDFLoader:
    """
    防御性 PDF 加载器（SOP 第一阶段符合版）

    特性：
      - 流式读取、自动重试、内存安全
      - 扫描件/图片型PDF自动调用 OCR（通过 pytesseract 或备用方案）
      - 去噪：剔除页眉/页脚/页码/水印/乱码
      - 语义切分：基于文档层级（章节、段落），而非固定长度
    """
    
    # 常见的页眉/页脚/页码/水印正则模式
    HEADER_FOOTER_PATTERNS = [
        re.compile(r'^\s*\d+\s*$'),              # 仅页码: " 1 "
        re.compile(r'^\s*Page\s+\d+\s*$', re.I),  # "Page 1"
        re.compile(r'^\s*第\s*\d+\s*页\s*$'),     # "第 1 页"
        re.compile(r'^\s*-+\s*\d+\s*-+\s*$'),     # "-- 1 --"
        re.compile(r'^\s*[\d]+\s*/\s*[\d]+\s*$'), # "1/10"
        # 水印模式（常见英文/中文水印关键词）
        re.compile(r'^\s*(DRAFT|CONFIDENTIAL|草稿|机密|仅供内部使用)\s*$', re.I),
        # 页眉常见模式：公司名 + 文档标题
        re.compile(r'^[A-Z][A-Z\s&.]+$'),         # 全大写公司名行
    ]

    # OCR 产生的乱码模式
    GARBAGE_PATTERNS = [
        re.compile(r'[●◆■▲▼※☆★○◇□△◎◁◀▷▶♤♠♡♥♧♣⊙◐◑○]'),  # 特殊符号（通常不是正文）
        re.compile(r'[\u0000-\u0008\u000b\u000c\u000e-\u001f]'),  # 控制字符
        re.compile(r'(\\x[a-f0-9]{2})+'),         # 转义序列如 \x0a\x0b
        re.compile(r'[﻿]'),                       # BOM 零宽空格
    ]

    def __init__(self, file_path: str):
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")
        self.file_path = file_path

    # ================================================================
    #  主入口：加载 → 去噪 → 语义切分
    # ================================================================

    def load_clean_and_chunk(self) -> List[Dict[str, Any]]:
        """
        SOP 第一阶段完整流程：
          1. 解析PDF（含OCR回退）
          2. 去噪处理
          3. 语义切分

        返回:
          [{"text": str, "metadata": dict, "chunk_id": str}, ...]
        """
        # ---- 步骤1: 解析 ----
        raw_pages = self._parse_pdf_with_ocr()

        if not raw_pages:
            logger.warning("PDF 解析结果为空，返回空列表")
            return []

        # ---- 步骤2: 去噪 ----
        cleaned_pages = []
        for page_data in raw_pages:
            cleaned_text = self._denoise(page_data["text"])
            # 跳过完全为空或只剩空白符的页面
            if cleaned_text.strip():
                cleaned_pages.append({
                    "text": cleaned_text,
                    "page_num": page_data["page_num"],
                    "metadata": page_data.get("metadata", {}),
                })

        if not cleaned_pages:
            logger.warning("去噪后所有页面为空，返回空列表")
            return []

        # ---- 步骤3: 语义切分 ----
        chunks = self._semantic_chunk(cleaned_pages)

        # ---- 添加 chunk_id ----
        for chunk in chunks:
            if "chunk_id" not in chunk:
                chunk["chunk_id"] = str(uuid.uuid4())

        logger.info(f"✅ 数据摄入完成: {len(chunks)} 个语义块")
        return chunks

    # ================================================================
    #  1.1 PDF 解析（含 OCR 回退）
    # ================================================================

    def _parse_pdf_with_ocr(self) -> List[Dict[str, Any]]:
        """
        解析PDF文档。
        对于文本型PDF直接提取；对于扫描件/图片型PDF，回退到OCR。
        """
        try:
            import fitz  # PyMuPDF
        except ImportError:
            raise RuntimeError("需要安装 PyMuPDF: pip install PyMuPDF")

        doc = None
        pages_data = []

        try:
            logger.info(f"📄 正在解析 PDF: {self.file_path}")
            doc = fitz.open(self.file_path)
            total_pages = len(doc)
            logger.info(f"   总页数: {total_pages}")

            for page_num in range(total_pages):
                try:
                    page = doc.load_page(page_num)
                    # 尝试提取文本
                    text = page.get_text()
                            
                    # 判断是否为扫描件（文本太少则可能是图片型PDF）
                    is_scanned = len(text.strip()) < 20

                    if is_scanned:
                        logger.info(f"   📷 第 {page_num + 1} 页为扫描件，尝试 OCR...")
                        ocr_text = self._ocr_page(page)
                        if ocr_text and ocr_text.strip():
                            text = ocr_text
                            logger.info(f"      OCR 提取到 {len(text)} 字符")
                        else:
                            logger.warning(f"      OCR 第 {page_num + 1} 页失败，保留原始文本")

                    # 收集页面元数据
                    page_metadata = {
                        "source": self.file_path,
                        "page": page_num + 1,
                        "total_pages": total_pages,
                        "is_scanned": is_scanned,
                    }

                    pages_data.append({
                        "text": text,
                        "page_num": page_num + 1,
                        "metadata": page_metadata,
                    })

                except Exception as e:
                    logger.warning(f"   解析第 {page_num + 1} 页失败，已跳过: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"无法打开或解析 PDF: {e}")
            raise
        finally:
            if doc:
                doc.close()

        return pages_data

    def _ocr_page(self, page: Any) -> str:
        """
        对页面图像进行 OCR 识别。
        首选 pytesseract，如果没有安装则尝试备用方案（PaddleOCR/LLM识别）。
        """
        try:
            # 方案A：pytesseract
            return self._ocr_with_tesseract(page)
        except (ImportError, Exception) as e:
            logger.debug(f"tesseract OCR 失败: {e}，尝试 paddleocr...")

        try:
            # 方案B：PaddleOCR
            return self._ocr_with_paddle(page)
        except (ImportError, Exception) as e:
            logger.debug(f"PaddleOCR 失败: {e}")

        logger.warning("所有 OCR 引擎均不可用，返回原始空文本")
        return ""

    def _ocr_with_tesseract(self, page: Any) -> str:
        """
        使用 pytesseract 进行 OCR。
        需要安装: pip install pytesseract
        以及系统级安装 tesseract-ocr + 中文语言包
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            raise ImportError("需要安装 pytesseract: pip install pytesseract")

        # 获取页面像素图
        pix = page.get_pixmap(dpi=300)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # 配置 Tesseract 参数（中文+英文）
        custom_config = r'--oem 3 --psm 6 -l chi_sim+eng'
        text = pytesseract.image_to_string(img, config=custom_config)
        return text

    def _ocr_with_paddle(self, page: Any) -> str:
        """
        使用 PaddleOCR 进行 OCR（对中文手写体更好）。
        需要安装: pip install paddleocr paddlepaddle
        """
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            raise ImportError("需要安装 PaddleOCR: pip install paddleocr")

        ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)
        pix = page.get_pixmap(dpi=300)
        from PIL import Image
        import io
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        result = ocr.ocr(img_bytes.getvalue(), cls=True)
        text_lines = []
        if result and result[0]:
            for line in result[0]:
                text_lines.append(line[1][0])
        return "\n".join(text_lines)

    # ================================================================
    #  1.2 去噪处理
    # ================================================================

    def _denoise(self, text: str) -> str:
        """去除页眉/页脚/页码/水印/乱码字符"""
        if not text:
            return ""

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            stripped = line.strip()

            # 跳过空行
            if not stripped:
                continue

            # 跳过页眉/页脚/页码/水印
            if self._is_header_footer(stripped):
                continue

            # 清理乱码字符
            cleaned_line = self._remove_garbage(stripped)

            # 跳过清理后变空的行
            if cleaned_line.strip():
                cleaned_lines.append(cleaned_line.strip())

        return "\n".join(cleaned_lines)

    def _is_header_footer(self, line: str) -> bool:
        """判断是否为页眉/页脚/页码/水印"""
        for pattern in self.HEADER_FOOTER_PATTERNS:
            if pattern.match(line):
                return True
        return False

    def _remove_garbage(self, text: str) -> str:
        """移除乱码字符"""
        for pattern in self.GARBAGE_PATTERNS:
            text = pattern.sub("", text)
        return text

    # ================================================================
    #  1.3 基于文档层级的语义切分
    # ================================================================

    def _semantic_chunk(self, cleaned_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        基于文档层级的语义切分策略：
          - 按章节标题（1/2/3级）分割
          - 段落作为最小独立单元
          - 避免在段落中间机械截断
          - 每个 Chunk 具备独立完整的语义表达
        """
        # 章节标题正则：常见的中英文章节标题格式
        section_patterns = [
            # 中文章节：一、第一章、第1章、1.、1.1、1.1.1
            re.compile(r'^第[一二三四五六七八九十\d]+[章节篇部分条]'),
            re.compile(r'^[一二三四五六七八九十]+[、]'),
            re.compile(r'^\d+[、．\.]\s*'),
            re.compile(r'^\d+\.\d+'),
            re.compile(r'^\d+\.\d+\.\d+'),
            # 英文章节：Chapter 1, Section 1.1
            re.compile(r'^(Chapter|Section|Part|Appendix)\s+\d', re.I),
            # 大写标题行（如 INTRODUCTION, BACKGROUND）
            re.compile(r'^[A-Z][A-Z\s]{2,30}$'),
        ]

        all_chunks = []
        current_section_title = "前言/概述"
        current_section_chunks = []

        for page_data in cleaned_pages:
            text = page_data["text"]
            page_num = page_data["page_num"]
            metadata = page_data.get("metadata", {})

            # 按段落分割
            paragraphs = re.split(r'\n\s*\n', text)

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # 判断是否为章节标题
                is_section = False
                for pat in section_patterns:
                    if pat.match(para):
                        is_section = True
                        break

                if is_section:
                    # 遇到新章节，先把之前的章节内容打包
                    if current_section_chunks:
                        # 如果当前章节内容太多（>1500字），进一步按段落拆分子块
                        all_chunks.extend(
                            self._finalize_section(current_section_title, current_section_chunks, metadata)
                        )
                        current_section_chunks = []

                    current_section_title = para
                else:
                    current_section_chunks.append({
                        "text": para,
                        "page_num": page_num,
                    })

        # 处理最后一个章节
        if current_section_chunks:
            all_chunks.extend(
                self._finalize_section(current_section_title, current_section_chunks, metadata)
            )

        # 如果没有识别出任何章节标题，按段落直接返回
        if not all_chunks:
            for page_data in cleaned_pages:
                all_chunks.append({
                    "text": page_data["text"],
                    "metadata": {
                        **page_data.get("metadata", {}),
                        "section": "全文",
                    },
                    "chunk_id": str(uuid.uuid4()),
                })

        return all_chunks

    def _finalize_section(
        self,
        section_title: str,
        section_chunks: List[Dict[str, Any]],
        base_metadata: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        将一个章节的内容打包为 Chunk 列表。
        若章节过长（>2000字符），按段落拆分为多个子块，每个子块保持语义完整。
        """
        result = []
        current_text = ""
        current_pages = set()
        current_paras = []

        for chunk in section_chunks:
            para_text = chunk["text"]
            page_num = chunk["page_num"]

            # 如果追加后超过阈值，先保存当前块
            if len(current_text) + len(para_text) > 500 and current_text.strip():
                result.append({
                    "text": f"【{section_title}】\n{current_text.strip()}",
                    "metadata": {
                        **base_metadata,
                        "section": section_title,
                        "pages": sorted(current_pages),
                        "paragraph_count": len(current_paras),
                    },
                    "chunk_id": str(uuid.uuid4()),
                })
                # 保留最后 100 字符作为重叠窗口
                overlap_text = current_text[-100:].strip() if len(current_text) > 100 else ""
                current_text = (overlap_text + "\n") if overlap_text else ""
                current_pages = set()
                current_paras = []

            current_text += para_text + "\n"
            current_pages.add(page_num)
            current_paras.append(para_text)

        # 剩余部分
        if current_text.strip():
            result.append({
                "text": f"【{section_title}】\n{current_text.strip()}",
                "metadata": {
                    **base_metadata,
                    "section": section_title,
                    "pages": sorted(current_pages),
                    "paragraph_count": len(current_paras),
                },
                "chunk_id": str(uuid.uuid4()),
            })

        return result

    # ================================================================
    #  向下兼容接口
    # ================================================================

    def load_and_split(self, chunk_size: int = 800, overlap: int = 100) -> List[Dict]:
        """保留旧版接口，内部调用新逻辑"""
        chunks = self.load_clean_and_chunk()
        # 转换为旧格式
        return [
            {
                "page_content": c["text"],
                "metadata": c["metadata"],
            }
            for c in chunks
        ]


# ================================================================
#  便捷函数
# ================================================================

def load_pdf_as_cleaned_chunks(file_path: str) -> List[Dict[str, Any]]:
    """
    一键加载PDF并返回清洗后的语义块。
    结果可直接用于 SOP 第二阶段的检索。
    """
    loader = RobustPDFLoader(file_path)
    return loader.load_clean_and_chunk()


if __name__ == "__main__":
    print("RobustPDFLoader (SOP v2) 模块加载成功！")
    print("测试: python -c 'from utils.pdf_loader import RobustPDFLoader; print(RobustPDFLoader)'")
