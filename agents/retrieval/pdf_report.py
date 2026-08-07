"""
PDF 报告生成器（通用版 — 支持任意章节结构 + Markdown 渲染）

替换 agents/retrieval/rag.py 中的 generate_pdf_report 函数。
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from tools.logger import get_logger

logger = get_logger(__name__)


def _get_cjk_font_name() -> str:
    """
    选择一个支持中文的字体。
    优先使用 PyMuPDF 内置 CJK 字体 china-s，如果不可用则尝试其他方案。
    最终回退到 china-ss。
    """
    import fitz
    import platform as _platform

    # 1. 尝试 PyMuPDF 内置 CJK 字体
    builtin_fonts = ["china-ss", "china-s", "china-st", "china-t", "DroidSansFallback"]
    for name in builtin_fonts:
        try:
            f = fitz.Font(fontname=name)
            tw = f.text_length("中国测试中文", fontsize=12)
            if tw > 10:
                return name
        except Exception:
            continue

    # 2. 尝试 fonts/ 目录下的自定义字体
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    fonts_dir = os.path.join(base_dir, "fonts")
    if os.path.isdir(fonts_dir):
        for fname in sorted(os.listdir(fonts_dir)):
            if fname.lower().endswith((".ttf", ".ttc", ".otf")):
                fpath = os.path.join(fonts_dir, fname)
                try:
                    f = fitz.Font(fontfile=fpath)
                    tw = f.text_length("中国测试中文", fontsize=12)
                    if tw > 10:
                        return fpath
                except Exception:
                    continue

    # 3. 尝试系统字体 (Windows)
    if _platform.system() == "Windows":
        win_dir = os.environ.get("WINDIR", "C:\\Windows")
        sys_fonts = [
            os.path.join(win_dir, "Fonts", "msyh.ttc"),
            os.path.join(win_dir, "Fonts", "simsun.ttc"),
            os.path.join(win_dir, "Fonts", "simhei.ttf"),
        ]
        for fp in sys_fonts:
            if os.path.exists(fp):
                try:
                    f = fitz.Font(fontfile=fp)
                    tw = f.text_length("中国测试中文", fontsize=12)
                    if tw > 10:
                        return fp
                except Exception:
                    continue

    # 4. 尝试下载 Noto Sans SC 字体
    try:
        os.makedirs(fonts_dir, exist_ok=True)
        cached = os.path.join(fonts_dir, "NotoSansSC-Regular.otf")
        if os.path.exists(cached) and os.path.getsize(cached) > 10000:
            try:
                f = fitz.Font(fontfile=cached)
                tw = f.text_length("中国测试中文", fontsize=12)
                if tw > 10:
                    return cached
            except Exception:
                pass

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
                if os.path.exists(cached):
                    try:
                        os.remove(cached)
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
    logger.warning("   ⚠️ 未找到中文字体，回退到 china-ss")
    return "china-ss"


def generate_pdf_report(report_json: Any, output_path: str) -> str:
    """
    生成带格式的 PDF 报告。
    支持任意章节结构，解析 Markdown 标题（## ### 等）。

    报告结构约定（JSON dict）：
    {
        "标题": "xxx",
        "行业现状": "xxx\\n## 子标题\\nxxx",
        "竞争格局": "xxx\\n- 列表项\\nxxx",
        "信息来源附录": [...]
    }
    """
    if isinstance(report_json, str):
        try:
            report_json = json.loads(report_json)
        except Exception:
            return _plaintext_fallback(report_json, output_path)
    if not isinstance(report_json, dict):
        return _plaintext_fallback(str(report_json), output_path)

    import fitz
    doc = fitz.open()
    fn = _get_cjk_font_name()
    font = fitz.Font(fontname=fn)
    pw, ph = 595, 842
    ml, mr, mt, mb = 45, 45, 40, 40
    cw = pw - ml - mr

    def new_page():
        return doc.new_page()

    _LINE_GAP = 4

    def write(x, y, text, size=10, color=(0, 0, 0)):
        doc[-1].insert_text((x, y), text, fontsize=size, fontname=fn, color=color)

    def wrap(text, size, max_w):
        lines = []
        if not text:
            return lines

        font_supports_cjk = False
        try:
            test_w = font.text_length("中文测试", size)
            font_supports_cjk = (test_w > 10)
        except Exception:
            font_supports_cjk = False

        def _line_width(line: str) -> float:
            if font is not None and font_supports_cjk:
                try:
                    return font.text_length(line, size)
                except Exception:
                    pass
            w = 0.0
            for ch in line:
                if ord(ch) > 127:
                    w += size * 1.0
                else:
                    w += size * 0.5
            return w

        if max_w < size * 2:
            max_w = size * 2

        while text:
            n = len(text)
            if _line_width(text) <= max_w:
                lines.append(text)
                break

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
                    hi = mid - 1
            if lo == 0:
                lo = 1
            lines.append(text[:lo])
            text = text[lo:]

        return lines

    def render(text, x, y, size=10, indent=0, max_w=None, color=(0, 0, 0)):
        if max_w is None:
            max_w = cw - indent
        min_max_w = int(cw * 0.4)
        if max_w < min_max_w:
            max_w = min_max_w
        lines = wrap(text, size, max_w)
        for line in lines:
            line_h = size + _LINE_GAP
            if y + line_h > ph - mb:
                new_page()
                y = mt
            doc[-1].insert_text((x + indent, y), line, fontsize=size, fontname=fn, color=color)
            y += line_h
        return y

    # ========== 开始渲染 ==========
    page = new_page()
    y = mt

    # 标题
    title = report_json.get("标题") or report_json.get("title") or "分析报告"
    write(ml, y, title, 18, (0.05, 0.20, 0.40))
    y += 26
    doc[-1].draw_line((ml, y), (pw - mr, y), color=(0.3, 0.6, 0.9), width=0.8)
    y += 12

    # ====== 通用章节渲染 ======
    # 定义渲染顺序（不在此列表中的字段按字母序）
    priority_keys = [
        "摘要", "执行摘要", "研究背景", "调研概述",
        "行业现状", "市场规模", "竞争格局",
        "产品与价格趋势", "商业模式",
        "行业挑战与风险", "总结与展望",
        "总结", "结论", "建议", "引用来源", "信息来源附录",
    ]

    all_keys = list(report_json.keys())
    ordered_keys = [k for k in priority_keys if k in report_json]
    remaining = [k for k in all_keys if k not in ordered_keys and k not in ("标题", "title")]
    remaining.sort()
    ordered_keys += remaining

    for key in ordered_keys:
        value = report_json[key]
        if not value:
            continue

        if key in ("标题", "title"):
            continue

        if y > ph - mb - 60:
            new_page()
            y = mt

        # 章节标题
        section_title = key
        write(ml, y, f"【{section_title}】", 14, (0.05, 0.20, 0.40))
        y += 20

        if isinstance(value, str):
            # 字符串：按行拆分，渲染 Markdown
            lines = value.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    y += 4
                    continue

                # 检测 Markdown 标题
                h_match = re.match(r'^(#{1,3})\s+(.*)', line)
                if h_match:
                    level = len(h_match.group(1))
                    h_text = h_match.group(2).strip()
                    # 去掉引用标记 [S1] 等
                    h_text = re.sub(r'\[S\d+\]', '', h_text).strip()
                    if y > ph - mb - 30:
                        new_page()
                        y = mt
                    if level == 1:
                        write(ml, y, h_text, 13, (0.05, 0.20, 0.40))
                        y += 18
                    elif level == 2:
                        write(ml, y, h_text, 12, (0.1, 0.3, 0.5))
                        y += 16
                    else:
                        write(ml, y, h_text, 11, (0.2, 0.3, 0.4))
                        y += 14
                    continue

                # 检测列表项
                if line.startswith('- ') or line.startswith('* '):
                    bullet = line[0]
                    content = line[2:].strip()
                    if y + size + _LINE_GAP > ph - mb:
                        new_page()
                        y = mt
                    doc[-1].insert_text((ml + 8, y), f"  {bullet} ", fontsize=10, fontname=fn, color=(0, 0, 0))
                    y = render(content, ml, y, 10, 24, color=(0.1, 0.1, 0.1))
                    continue

                # 普通段落
                y = render(line, ml, y, 10, 8)

            y += 6

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if y > ph - mb - 20:
                            new_page()
                            y = mt
                        label = f"{k}: " if k else ""
                        if isinstance(v, str):
                            y = render(f"{label}{v}", ml, y, 10, 12)
                        elif isinstance(v, list):
                            y = render(f"{label}{', '.join(str(x) for x in v)}", ml, y, 10, 12)
                    y += 4
                elif isinstance(item, str):
                    if y > ph - mb - 20:
                        new_page()
                        y = mt
                    y = render(item, ml, y, 10, 12)

        elif isinstance(value, dict):
            for k, v in value.items():
                if y > ph - mb - 20:
                    new_page()
                    y = mt
                label = f"{k}: " if k else ""
                if isinstance(v, str):
                    y = render(f"{label}{v}", ml, y, 10, 12)
                elif isinstance(v, list):
                    items = ', '.join(str(x) for x in v)
                    y = render(f"{label}{items}", ml, y, 10, 12)

    # 页码
    for i in range(doc.page_count):
        doc[i].insert_text((pw - 50, ph - 25), str(i + 1), fontsize=8, fontname=fn, color=(0.7, 0.7, 0.7))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path


def _plaintext_fallback(text: str, output_path: str) -> str:
    """纯文本回退，安全分页排版。"""
    import fitz
    doc = fitz.open()
    fn = _get_cjk_font_name()
    pw, ph = 595, 842
    margin = 50
    max_line_w = pw - 2 * margin - 10
    font_size = 10
    line_height = font_size + 4
    content_h = ph - 2 * margin
    max_lines_per_page = int(content_h / line_height)

    page = doc.new_page()
    lines_on_page = 0

    def _char_width(ch: str) -> float:
        return font_size * 0.85 if ord(ch) > 127 else font_size * 0.45

    def _split_line(text: str) -> str:
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


# ============================================================
#  前端兼容入口：给 frontend_report_pdf 专用的轻量包装
# ============================================================

def generate_frontend_pdf(report_data: dict, title: str, output_path: str) -> str:
    """
    前端兼容的 PDF 生成入口。

    被 business/market_research/api.py 中的 frontend_report_pdf 调用。

    参数:
      report_data:  报告字典（可包含任意 key：标题/摘要/行业现状/竞争格局等）
      title:        报告标题（若 report_data 中无标题，则使用此参数）
      output_path:  输出 PDF 文件路径

    返回:
      output_path（成功时）
    """
    # 确保标题字段存在
    if '标题' not in report_data and 'title' not in report_data:
        report_data['标题'] = title

    # 委托给完整的 generate_pdf_report
    return generate_pdf_report(report_data, output_path)
