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

def wrap_text_no_cut_chinese(text, max_width, fontname, fontsize=10):
    """中文安全换行，绝不切割单个汉字，使用 fontname 字符串"""
    import fitz
    font = fitz.Font(fontname=fontname)
    lines = []
    current_line = []
    current_w = 0
    for ch in text:
        w = font.text_length(ch, fontsize=fontsize)
        if current_w + w > max_width and current_line:
            lines.append("".join(current_line))
            current_line = []
            current_w = 0
        current_line.append(ch)
        current_w += w
    if current_line:
        lines.append("".join(current_line))
    return lines

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


# ============================================================
#  Markdown 行内标记清理：移除语法标记，保留纯文本内容
# ============================================================
def _strip_markdown_inline(text: str) -> str:
    """
    移除行内 Markdown 语法标记，保留纯文本内容。
    用于 PyMuPDF 渲染前清理，因为 PDF 不支持行内富文本。
    """
    if not text:
        return text
    # 图片：![alt](url) → [图片: alt]
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'[图片: \1]', text)
    # 链接：[text](url) → text（url）
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1（\2）', text)
    # 加粗：**text** → text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # 斜体：*text* → text（不匹配加粗的**）
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'\1', text)
    # 行内代码：`code` → code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # 删除线：~~text~~ → text
    text = re.sub(r'~~([^~]+)~~', r'\1', text)
    return text


# ============================================================
#  Markdown 归一化：将各种 LLM 输出的格式统一为 PDF 可解析的标准格式
# ============================================================
def _normalize_markdown_for_pdf(text: str) -> str:
    """
    将各种 LLM 输出的 Markdown 格式统一为 PDF 生成器能识别的标准格式。

    Cloud 模型（如 DeepSeek）通常输出标准 Markdown: ## 标题, - 列表
    Local 模型（如 Qwen 本地版）可能输出: **粗体标题**, * 列表, 数字序号

    归一化规则：
    1. **粗体文本**（单独成行且无其他内容）→ ## 标题
    2. * 列表项 → - 列表项（统一前缀）
    3. 移除过多空行，但不破坏段落结构
    4. 保留行内 **粗体**（不做转换，避免误伤）
    """
    if not text:
        return text

    lines = text.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            result.append("")
            continue

        # 【已注释】规则1：**粗体文本** 单独成行 → ## 标题（太激进，会误伤正文）
        # bold_only = re.match(
        #     r'^\s*\*\*([^*]+)\*\*\s*(\[S?\d*\])?\s*$',
        #     stripped,
        # )
        # if bold_only:
        #     title_text = bold_only.group(1).strip()
        #     result.append(f"## {title_text}")
        #     continue

        # 规则2：* 列表项 → - 列表项
        if stripped.startswith('* '):
            content = stripped[2:]
            result.append(f"- {content}")
            continue

        # 其他行保持原样
        result.append(line)

    return '\n'.join(result)


def generate_pdf_report(report_json: Any, output_path: str) -> str:
    """
    Generate a formatted PDF report using PyMuPDF insert_textbox for auto-wrapping.
    Supports arbitrary section structures and Markdown titles (## ### etc.).

    Report structure (JSON dict):
    {
        "标题": "xxx",
        "行业现状": "xxx\n## 子标题\nxxx",
        "竞争格局": "xxx\n- 列表项\nxxx",
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

    # ========== Normalize all string values (support various LLM output formats) ==========
    for key in report_json:
        if isinstance(report_json[key], str):
            report_json[key] = _normalize_markdown_for_pdf(report_json[key])
        elif isinstance(report_json[key], list):
            report_json[key] = [
                _normalize_markdown_for_pdf(item) if isinstance(item, str) else item
                for item in report_json[key]
            ]
        elif isinstance(report_json[key], dict):
            for sub_key in report_json[key]:
                if isinstance(report_json[key][sub_key], str):
                    report_json[key][sub_key] = _normalize_markdown_for_pdf(report_json[key][sub_key])

    import fitz
    doc = fitz.open()
    fn = _get_cjk_font_name()
    font = fitz.Font(fontname=fn)
    pw, ph = 595, 842  # A4
    ml, mr, mt, mb = 50, 50, 50, 50
    cw = pw - ml - mr  # content width

    # Helper: write a single line of text at (x, y) — y 是文本基线
    def write_line(x, y, text, size=10, color=(0, 0, 0)):
        doc[-1].insert_text((x, y), text, fontsize=size, fontname=fn, color=color)

    # Helper: render multi-line text with safe Chinese wrapping
    def render_textbox(text, x, y, w, size=10, color=(0,0,0), line_height=1.25):
        """
        中文安全换行，绝不切割汉字。
        利用模块级 wrap_text_no_cut_chinese 预先拆分行，再逐行 insert_text 绘制。
        返回更新后的 y 坐标。
        """
        if not text:
            return y

        usable_w = w * 0.88  # 留 12% 右边距，避免 font.text_length() 测量误差导致的溢出
        lines = wrap_text_no_cut_chinese(text, usable_w, fn, size)
        lh = size * line_height

        for line in lines:
            if y + lh > ph - mb - 5:
                doc.new_page()
                y = mt
            # 用 clip 限制绘制区域，防止测量误差导致的溢出
            clip_rect = fitz.Rect(x, y - size, x + usable_w + 5, y + size * 2)
            doc[-1].insert_text((x, y), line, fontsize=size, fontname=fn, color=color, clip=clip_rect)
            y += lh
        return y

    # ========== Begin rendering ==========
    page = doc.new_page()
    y = mt

    # Title
    title = report_json.get("标题") or report_json.get("title") or "分析报告"
    write_line(ml, y, title, 18, (0.05, 0.20, 0.40))
    y += 22
    doc[-1].draw_line((ml, y), (pw - mr, y), color=(0.3, 0.6, 0.9), width=0.8)
    y += 10

    # ====== Section rendering ======
    priority_keys = [
        "摘要", "执行摘要", "研究背景", "调研概述",
        "行业现状", "市场规模", "竞争格局",
        "产品与价格趋势", "商业模式",
        "行业挑战与风险", "总结与展望",
        "总结", "结论", "建议", "引用来源",
        "竞品分析", "机会与风险", "信息来源附录",
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

        # Check if we need a new page
        if y > ph - mb - 60:
            page = doc.new_page()
            y = mt

        # Section title — 加字体高度，因为 write_line 的 y 是基线，而 render_textbox 返回的是文本底部
        y += 18
        write_line(ml, y, f"【{key}】", 14, (0.05, 0.20, 0.40))
        y += 12

        if isinstance(value, str):
            # Process string: split by lines, detect Markdown headers
            raw_lines = value.split('\n')
            for raw_line in raw_lines:
                stripped = raw_line.strip()
                if not stripped:
                    y += 4
                    continue

                # 中文编号章节标题：一、市场发展现状
                cn_h_match = re.match(r'^([一二三四五六七八九十]+)[、.．]\s*(.*)', stripped)
                if cn_h_match:
                    cn_num = cn_h_match.group(1)
                    cn_title = cn_h_match.group(2).strip()
                    cn_title = re.sub(r'\[S\d+\]', '', cn_title).strip()
                    if y > ph - mb - 40:
                        page = doc.new_page()
                        y = mt
                    y += 4
                    write_line(ml, y, f"{cn_num}、{cn_title}", 13, (0.05, 0.20, 0.40))
                    y += 12
                    continue

                # 数字编号子标题：1.1 全球市场规模与增长
                num_h_match = re.match(r'^(\d+\.\d+)\s+(.*)', stripped)
                if num_h_match:
                    num_id = num_h_match.group(1)
                    num_title = num_h_match.group(2).strip()
                    num_title = re.sub(r'\[S\d+\]', '', num_title).strip()
                    if y > ph - mb - 40:
                        page = doc.new_page()
                        y = mt
                    y += 4
                    write_line(ml, y, f"{num_id} {num_title}", 12, (0.1, 0.3, 0.5))
                    y += 10
                    continue

                # Markdown heading
                h_match = re.match(r'^(#{1,3})\s+(.*)', stripped)
                if h_match:
                    level = len(h_match.group(1))
                    h_text = re.sub(r'\[S\d+\]', '', h_match.group(2)).strip()
                    h_text = _strip_markdown_inline(h_text)
                    if y > ph - mb - 40:
                        page = doc.new_page()
                        y = mt
                    y += 4
                    if level == 1:
                        write_line(ml, y, h_text, 13, (0.05, 0.20, 0.40))
                        y += 12
                    elif level == 2:
                        write_line(ml, y, h_text, 12, (0.1, 0.3, 0.5))
                        y += 10
                    else:
                        write_line(ml, y, h_text, 11, (0.2, 0.3, 0.4))
                        y += 8
                    continue

                # List item — 支持嵌套缩进
                list_match = re.match(r'^([ \t]*)([-*])\s+(.*)', raw_line)
                if list_match:
                    leading_spaces = len(list_match.group(1))
                    list_prefix = list_match.group(2)  # '-' or '*'
                    content = list_match.group(3).strip()
                    content = _strip_markdown_inline(content)

                    # 计算嵌套层级：每2个空格=一级
                    nest_level = max(0, leading_spaces // 2)
                    # 基础缩进：一级=12，二级=24，三级=36
                    base_indent = ml + 12 + nest_level * 12
                    # bullet 缩进比文字少 16
                    bullet_x = base_indent - 16

                    if y + 14 > ph - mb - 10:
                        page = doc.new_page()
                        y = mt
                    write_line(bullet_x, y, "  • ", 10, (0.1, 0.1, 0.1))
                    y = render_textbox(content, base_indent, y, cw - (base_indent - ml), 10, (0.1, 0.1, 0.1))
                    continue

                # Normal paragraph — 清理 Markdown 行内标记
                cleaned_line = _strip_markdown_inline(stripped)
                if y + 14 > ph - mb - 10:
                    page = doc.new_page()
                    y = mt
                y = render_textbox(cleaned_line, ml + 8, y, cw - 8, 10, (0.1, 0.1, 0.1))

            y += 3

        elif isinstance(value, list):
            for item_idx, item in enumerate(value):
                if isinstance(item, dict):
                    if any(k in item for k in ("竞品名称", "产品类型", "性能参数", "定价区间", "分析")):
                        if y > ph - mb - 40:
                            page = doc.new_page()
                            y = mt
                        name = item.get('竞品名称', '')
                        write_line(ml, y, f"▎ {item_idx + 1}. {name}", 12, (0.05, 0.20, 0.40))
                        y += 18
                        for k, v in item.items():
                            if k == "竞品名称":
                                continue
                            if y > ph - mb - 40:
                                page = doc.new_page()
                                y = mt
                            if isinstance(v, str):
                                text = f"▪ {k}：{_strip_markdown_inline(v)}"
                                y = render_textbox(text, ml + 16, y, cw - 16, 10, (0.2, 0.2, 0.2))
                        y += 6
                    else:
                        for k, v in item.items():
                            if y > ph - mb - 40:
                                page = doc.new_page()
                                y = mt
                            label = f"{k}: " if k else ""
                            if isinstance(v, str):
                                text = f"{label}{_strip_markdown_inline(v)}"
                                y = render_textbox(text, ml + 12, y, cw - 12, 10, (0.1, 0.1, 0.1))
                            elif isinstance(v, list):
                                cleaned_list = [_strip_markdown_inline(str(x)) for x in v]
                                text = f"{label}{', '.join(cleaned_list)}"
                                y = render_textbox(text, ml + 12, y, cw - 12, 10, (0.1, 0.1, 0.1))
                        y += 4
                elif isinstance(item, str):
                    if y > ph - mb - 40:
                        page = doc.new_page()
                        y = mt
                    y = render_textbox(_strip_markdown_inline(item), ml + 12, y, cw - 12, 10, (0.1, 0.1, 0.1))

        elif isinstance(value, dict):
            for k, v in value.items():
                if y > ph - mb - 40:
                    page = doc.new_page()
                    y = mt
                label = f"{k}: " if k else ""
                if isinstance(v, str):
                    text = f"{label}{_strip_markdown_inline(v)}"
                    y = render_textbox(text, ml + 12, y, cw - 12, 10, (0.1, 0.1, 0.1))
                elif isinstance(v, list):
                    text = label
                    y = render_textbox(text, ml + 12, y, cw - 12, 10, (0.1, 0.1, 0.1))
                    for item_val in v:
                        y = render_textbox(f"• {_strip_markdown_inline(str(item_val))}", ml + 24, y, cw - 24, 10, (0.2, 0.2, 0.2))

    # Page numbers
    for i in range(doc.page_count):
        doc[i].insert_text((pw - 50, ph - 25), str(i + 1), fontsize=8, fontname=fn, color=(0.7, 0.7, 0.7))

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    doc.save(output_path)
    doc.close()
    return output_path


def _plaintext_fallback(text: str, output_path: str) -> str:
    """纯文本回退，使用 insert_textbox 自动换行。"""
    import fitz
    doc = fitz.open()
    fn = _get_cjk_font_name()
    pw, ph = 595, 842  # A4
    ml, mr, mt, mb = 50, 50, 50, 50
    cw = pw - ml - mr
    font_size = 11
    line_spacing = 1.5

    page = doc.new_page()
    y = mt

    for para in text.replace("\r\n", "\n").split("\n"):
        if not para.strip():
            y += font_size * 0.6
            if y > ph - mb - font_size * 2:
                page = doc.new_page()
                y = mt
            continue

        # Render paragraph, handling overflow by creating new pages
        remaining = para
        while remaining:
            avail_h = ph - mb - y - 10
            if avail_h < font_size * line_spacing:
                page = doc.new_page()
                y = mt
                avail_h = ph - mb - y - 10

            rect = fitz.Rect(ml, y, ml + cw, y + avail_h)
            overflow_h = page.insert_textbox(rect, remaining, fontsize=font_size, fontname=fn, lineheight=line_spacing)

            # Estimate lines that fit
            chars_per_line = max(1, int(cw / (font_size * 0.6)))
            total_lines = max(1, (len(remaining) + chars_per_line - 1) // chars_per_line)

            if overflow_h > 0:
                # Estimate how many lines fit
                avail_lines = max(1, int(avail_h / (font_size * line_spacing)))
                fitted_lines = min(total_lines, avail_lines)
            else:
                fitted_lines = total_lines

            y += fitted_lines * font_size * line_spacing + 2
            remaining = ''  # insert_textbox handles overflow; we don't need to split manually

            # If overflow_h > 0, text was truncated; we need to render the rest
            # But insert_textbox just clips; it doesn't return the truncated text
            # So we break and move on
            break

    # Page numbers
    for i in range(doc.page_count):
        doc[i].insert_text((pw - 50, ph - 25), str(i + 1), fontsize=8, fontname=fn, color=(0.7, 0.7, 0.7))

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
