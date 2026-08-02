"""信源溯源与冲突识别管理器

负责：
1. 为每一条检索结果生成标准化引用元数据（ref_id, 来源类型, 文档名, 页码, 链接, 置信权重）
2. 检测 PDF 与网络来源之间的信息冲突
3. 在最终报告中自动生成角标引用和参考文献清单
"""

import re
from typing import Any, Dict, List, Optional

from core.utils.logger import get_logger

logger = get_logger(__name__)

# 默认置信权重
CONFIDENCE_PDF = 0.9      # 内部保密文档
CONFIDENCE_WEB = 0.6      # 外网公开资讯


def build_citation_metadata(source_materials: List[Dict]) -> List[Dict]:
    """
    为检索结果中的每一条素材生成标准化引用元数据。

    参数:
      source_materials: 检索节点输出的素材列表，每项包含:
        - text: 素材文本
        - source_type: "pdf" | "web"
        - source_index: 来源索引
        - trust_tier: "verified" | "unverified" | "low_quality"
        - source_url: 网页链接（web来源）
        - metadata: 元数据（PDF来源，含 doc_name, page_num 等）

    返回:
      [
        {
          "ref_id": 1,                 # 引用编号 [1]
          "source_type": "pdf",
          "doc_name": "2024行业报告.pdf",
          "page_num": 15,
          "url": "",
          "snippet": "原文摘要...",
          "confidence_weight": 0.9,
          "trust_tier": "verified",
        },
        ...
      ]
    """
    citation_list = []
    ref_counter = 1

    for item in source_materials:
        if not isinstance(item, dict):
            continue

        source_type = item.get("source_type", "unknown")
        trust_tier = item.get("trust_tier", "unverified")
        text = item.get("text", "")[:200]  # 仅取前200字作为摘要

        # 基础结构
        entry: Dict[str, Any] = {
            "ref_id": ref_counter,
            "source_type": source_type,
            "doc_name": "",
            "page_num": 0,
            "url": "",
            "snippet": text,
            "confidence_weight": CONFIDENCE_PDF if source_type == "pdf" else CONFIDENCE_WEB,
            "trust_tier": trust_tier,
        }

        if source_type == "pdf":
            # 尝试从 metadata 中提取文档名和页码
            metadata = item.get("metadata", {}) or {}
            if isinstance(metadata, dict):
                entry["doc_name"] = metadata.get("doc_name", metadata.get("source", "内部文档"))
                entry["page_num"] = metadata.get("page_num", metadata.get("page", 0))
            else:
                entry["doc_name"] = "内部文档"
            entry["confidence_weight"] = CONFIDENCE_PDF

        elif source_type == "web":
            entry["url"] = item.get("source_url", "")
            entry["doc_name"] = ""
            entry["page_num"] = 0
            entry["confidence_weight"] = CONFIDENCE_WEB

        citation_list.append(entry)
        ref_counter += 1

    logger.info(f"📝 [CitationManager] 生成 {len(citation_list)} 条引用元数据")
    return citation_list


def detect_conflicts(
    pdf_materials: List[Dict],
    web_materials: List[Dict],
    citation_metadata: List[Dict],
) -> List[Dict]:
    """
    检测 PDF 与网络来源之间的信息冲突。

    策略：
    - 提取 PDF 和 Web 素材的关键实体/数值
    - 对比相同主题的陈述是否一致
    - 冲突时标记 "conflict"，系统默认采信高权重 PDF 来源

    参数:
      pdf_materials: PDF 来源的素材列表
      web_materials: 网络来源的素材列表
      citation_metadata: 引用元数据列表

    返回:
      [
        {
          "topic": "冲突主题",
          "pdf_statement": "PDF 观点",
          "web_statement": "网络观点",
          "resolution": "优先采信内部文档（置信权重0.9）",
          "status": "conflict" | "consistent",
        }
      ]
    """
    conflicts = []

    if not pdf_materials or not web_materials:
        return conflicts

    # 提取 PDF 和 Web 的关键数字/百分比
    pdf_numbers = _extract_key_numbers(" ".join([m.get("text", "") for m in pdf_materials]))
    web_numbers = _extract_key_numbers(" ".join([m.get("text", "") for m in web_materials]))

    # 对比重叠的数字/百分比
    common_labels = set(pdf_numbers.keys()) & set(web_numbers.keys())
    for label in common_labels:
        pdf_val = pdf_numbers[label]
        web_val = web_numbers[label]

        # 如果数值不同，判定为冲突
        if pdf_val != web_val:
            # 尝试数值比较
            try:
                pdf_num = float(re.sub(r'[^0-9.\-]', '', pdf_val))
                web_num = float(re.sub(r'[^0-9.\-]', '', web_val))
                diff_ratio = abs(pdf_num - web_num) / max(abs(pdf_num), abs(web_num), 0.01)
                if diff_ratio < 0.05:  # 差异小于5%认为一致
                    continue
            except ValueError:
                pass

            # 查找对应的原文
            pdf_ctx = _find_context(" ".join([m.get("text", "")[:500] for m in pdf_materials]), label, 80)
            web_ctx = _find_context(" ".join([m.get("text", "")[:500] for m in web_materials]), label, 80)

            conflicts.append({
                "topic": label,
                "pdf_statement": pdf_ctx or f"PDF: {pdf_val}",
                "web_statement": web_ctx or f"网络: {web_val}",
                "resolution": f"优先采信内部文档（置信权重{CONFIDENCE_PDF}），完整备注外网不同观点",
                "status": "conflict",
            })

    if conflicts:
        logger.warning(f"⚠️ [CitationManager] 检测到 {len(conflicts)} 处信息冲突")
        for c in conflicts:
            logger.warning(f"   🔴 冲突: {c['topic']} | PDF: {c['pdf_statement'][:50]}... | Web: {c['web_statement'][:50]}...")
    else:
        logger.info("✅ [CitationManager] 未检测到信息冲突")

    return conflicts


def generate_references_section(citation_metadata: List[Dict]) -> str:
    """
    生成文末参考文献清单（Markdown格式）。

    参数:
      citation_metadata: 引用元数据列表

    返回:
      Markdown 格式的参考文献清单
    """
    if not citation_metadata:
        return ""

    lines = ["## 参考文献\n", ""]

    for cit in citation_metadata:
        ref_id = cit.get("ref_id", 0)
        source_type = cit.get("source_type", "unknown")
        snippet = cit.get("snippet", "")[:80]

        if source_type == "pdf":
            doc_name = cit.get("doc_name", "内部文档")
            page_num = cit.get("page_num", 0)
            page_str = f"，第{page_num}页" if page_num else ""
            lines.append(
                f"[{ref_id}] 📄【内部文档信息】{doc_name}{page_str} — {snippet}..."
            )
        elif source_type == "web":
            url = cit.get("url", "")
            url_display = url if url else "（无链接）"
            lines.append(
                f"[{ref_id}] 🌐【公开网络信息】{url_display} — {snippet}..."
            )
        else:
            lines.append(f"[{ref_id}] {snippet}...")

        lines.append("")  # 空行分隔

    return "\n".join(lines)


def generate_conflict_alerts_section(conflict_alerts: List[Dict]) -> str:
    """
    生成冲突预警可视化标记。

    参数:
      conflict_alerts: 冲突检测结果列表

    返回:
      Markdown 格式的冲突预警区块
    """
    if not conflict_alerts:
        return ""

    lines = ["## 信源冲突预警\n", ""]

    for conflict in conflict_alerts:
        status = conflict.get("status", "conflict")
        topic = conflict.get("topic", "")

        if status == "conflict":
            lines.append(f"🔴 **冲突预警 — {topic}**\n")
            lines.append(f"- 📄 **内部文档观点**: {conflict.get('pdf_statement', '')}\n")
            lines.append(f"- 🌐 **外网公开信息**: {conflict.get('web_statement', '')}\n")
            lines.append(f"- ⚖️ **处理方式**: {conflict.get('resolution', '')}\n")
            lines.append("\n---\n")
        else:
            lines.append(f"🟢 **信息一致 — {topic}**\n")
            lines.append(f"- {conflict.get('pdf_statement', '')}\n")
            lines.append("\n---\n")

    return "\n".join(lines)


def _extract_key_numbers(text: str) -> Dict[str, str]:
    """
    从文本中提取关键数字/百分比及其上下文标签。

    返回格式: {"标签": "数值"}
    例如: {"市场占有率": "35%", "增长率": "12.5%"}
    """
    result = {}

    # 匹配 "XX 为 YY%" 或 "XX 达到 YY" 等模式
    patterns = [
        r'([\u4e00-\u9fff\w]{2,10})(?:为|达到|是|约|有|增长|下降|占比)([0-9]+(?:\.[0-9]+)?%?)',
        r'([\u4e00-\u9fff\w]{2,10})\s*[：:]\s*([0-9]+(?:\.[0-9]+)?%?)',
        r'([0-9]+(?:\.[0-9]+)?%?)\s*(?:的|之)?([\u4e00-\u9fff\w]{2,10})',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) >= 2:
                label = match[0].strip() if match[0].strip() else match[1].strip()
                value = match[1].strip() if match[0].strip() else match[0].strip()
                if len(label) >= 2:
                    result[label] = value

    return result


def _find_context(text: str, keyword: str, window: int = 80) -> str:
    """在文本中定位关键词并返回上下文片段"""
    idx = text.find(keyword)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(text), idx + len(keyword) + window)
    ctx = text[start:end]
    if start > 0:
        ctx = "..." + ctx
    if end < len(text):
        ctx = ctx + "..."
    return ctx