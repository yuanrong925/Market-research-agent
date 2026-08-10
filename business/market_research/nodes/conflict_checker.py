"""
【轻量化】多源数据冲突检测节点 — 检索后、分析前

功能：
  1. 从 PDF 和 Web 素材中通过正则提取数值（市场规模、增长率、营收、价格等）
  2. 对比同一主题的数值是否一致
  3. 发现冲突时标记数据分歧，附上两类数据的原始来源链接
  4. 不修改任何检索结果，仅在 state 中写入冲突标记

边界控制：
  - 仅文本正则提取，不引入 PDF 表格解析、OCR
  - 不改动 retrieval.py 和任何检索主流程
  - 不写入 core/ 目录
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from core.utils.logger import get_logger

logger = get_logger(__name__)

# ============================================================
#  市场调研量化指标正则模式
# ============================================================
# 匹配模式：数字 + 单位/百分号，前面带上下文关键词
QUANTITY_PATTERNS = [
    # 市场规模、营收等金额类
    re.compile(
        r'(?:市场规模|市场容量|营收|收入|销售额|产值|GMV|交易额|投资额|融资额|金额|总值)'
        r'[：:是为达到约增长超突破达]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:万亿?|亿|万?元|美元|欧元|人民币|港币|美元|欧元)'
    ),
    # 增长率/增速
    re.compile(
        r'(?:增长率|增速|同比增长|环比增长|年增长|增长|增幅|下降|下滑|下跌|涨幅|跌幅)'
        r'[：:是为达到约]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*%'
    ),
    # 百分比/占比/份额
    re.compile(
        r'(?:占比|份额|市占率|市场占有率|渗透率|普及率|覆盖率|毛利率|净利率|利润率|税率)'
        r'[：:是为达到约]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*%'
    ),
    # 价格类
    re.compile(
        r'(?:单价|价格|售价|定价|均价|客单价|客单)'
        r'[：:是为达到约在]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:元|美元|欧元|人民币|港币|日元)'
    ),
    # 数量类（台、件、个、吨等）
    re.compile(
        r'(?:产量|销量|出货量|库存|产能|装机量|保有量)'
        r'[：:是为达到约]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:万|亿)?\s*(?:台|件|个|吨|只|辆|套|千瓦时|MWh|GWh)'
    ),
    # 年份 + 数字模式（如：2024年达到500亿）
    re.compile(
        r'(?:20[0-9]{2})年\s*[达到预计将突破]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*(?:万亿?|亿|万?元|美元|欧元|人民币)'
    ),
    # 年份 + 增长率模式（如：2024年同比增长20%）
    re.compile(
        r'(?:20[0-9]{2})年\s*(?:同比增长|增长|增速|下降|下滑)[：:为]?\s*'
        r'([0-9]+(?:\.[0-9]+)?)\s*%'
    ),
]


def extract_quantities(text: str) -> List[Dict[str, Any]]:
    """
    从文本中提取所有量化指标数值。

    返回:
      [
        {
          "label": "市场规模",
          "value": "5000",
          "unit": "亿元",
          "raw": "市场规模达到5000亿元",
          "context": "...
        },
        ...
      ]
    """
    results = []
    for pattern in QUANTITY_PATTERNS:
        for match in pattern.finditer(text):
            full_match = match.group(0)
            num_val = match.group(1)
            # 确定上下文标签（取匹配前20字）
            start = max(0, match.start() - 20)
            context = text[start:match.end() + 20]

            # 提取标签
            label = ""
            for kw in ["市场规模", "增长率", "营收", "收入", "销售额", "占比", "份额",
                        "市占率", "单价", "价格", "毛利率", "净利率", "渗透率",
                        "产量", "销量", "出货量", "库存", "产能"]:
                if kw in full_match:
                    label = kw
                    break

            results.append({
                "label": label or "量化指标",
                "value": num_val,
                "unit": _extract_unit(full_match),
                "raw": full_match[:80],
                "context": context[:120],
            })

    return results


def _extract_unit(text: str) -> str:
    """从文本中提取单位"""
    unit_patterns = [
        (r'(万亿?|亿|万?元|美元|欧元|人民币|港币)', "金额"),
        (r'%', "%"),
        (r'(台|件|个|吨|只|辆|套|千瓦时|MWh|GWh)', "数量"),
    ]
    for pat, _ in unit_patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return ""


def _get_source_link(item: Dict[str, Any]) -> str:
    """从素材项中提取来源链接"""
    source_type = item.get("source_type", "")
    if source_type == "web":
        return item.get("source_url", "")
    elif source_type == "pdf":
        metadata = item.get("metadata", {}) or {}
        doc_name = metadata.get("doc_name", metadata.get("source", "内部文档"))
        page = metadata.get("page_num", metadata.get("page", ""))
        return f"{doc_name}" + (f" 第{page}页" if page else "")
    return ""


def _group_by_label(items: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
    """按标签对提取的数值进行分组"""
    groups: Dict[str, List[Dict]] = {}
    for item in items:
        label = item.get("label", "其他")
        if label not in groups:
            groups[label] = []
        groups[label].append(item)
    return groups


def _compare_values(
    pdf_values: List[Dict[str, Any]],
    web_values: List[Dict[str, Any]],
    pdf_materials: List[Dict[str, Any]],
    web_materials: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    对比 PDF 和 Web 来源的量化数值，检测冲突。

    返回:
      [
        {
          "label": "市场规模",
          "pdf_value": "5000",
          "pdf_unit": "亿元",
          "pdf_source": "内部文档 第15页",
          "web_value": "4800",
          "web_unit": "亿元",
          "web_source": "https://...",
          "status": "conflict" | "consistent",
          "diff_ratio": 0.04,
        }
      ]
    """
    conflicts = []

    pdf_groups = _group_by_label(pdf_values)
    web_groups = _group_by_label(web_values)

    # 取 PDF 和 Web 共有的标签
    common_labels = set(pdf_groups.keys()) & set(web_groups.keys())

    for label in common_labels:
        pdf_list = pdf_groups[label]
        web_list = web_groups[label]

        # 取每组第一个数值作为代表
        pdf_item = pdf_list[0]
        web_item = web_list[0]

        try:
            pdf_num = float(re.sub(r'[^0-9.\-]', '', pdf_item["value"]))
            web_num = float(re.sub(r'[^0-9.\-]', '', web_item["value"]))

            # 计算差异比例
            max_val = max(abs(pdf_num), abs(web_num), 0.01)
            diff_ratio = abs(pdf_num - web_num) / max_val

            if diff_ratio < 0.05:
                # 差异小于5%，认为一致
                conflicts.append({
                    "label": label,
                    "pdf_value": pdf_item["value"],
                    "pdf_unit": pdf_item.get("unit", ""),
                    "pdf_context": pdf_item.get("context", ""),
                    "web_value": web_item["value"],
                    "web_unit": web_item.get("unit", ""),
                    "web_context": web_item.get("context", ""),
                    "status": "consistent",
                    "diff_ratio": round(diff_ratio, 4),
                })
            else:
                # 差异大于5%，标记冲突
                # 查找对应的原始素材来源链接
                pdf_source = ""
                web_source = ""
                for m in pdf_materials:
                    if pdf_item["raw"][:20] in m.get("text", ""):
                        pdf_source = _get_source_link(m)
                        break
                for m in web_materials:
                    if web_item["raw"][:20] in m.get("text", ""):
                        web_source = _get_source_link(m)
                        break

                conflicts.append({
                    "label": label,
                    "pdf_value": pdf_item["value"],
                    "pdf_unit": pdf_item.get("unit", ""),
                    "pdf_context": pdf_item.get("context", ""),
                    "pdf_source": pdf_source,
                    "web_value": web_item["value"],
                    "web_unit": web_item.get("unit", ""),
                    "web_context": web_item.get("context", ""),
                    "web_source": web_source,
                    "status": "conflict",
                    "diff_ratio": round(diff_ratio, 4),
                })
        except (ValueError, TypeError):
            continue

    # 检测 PDF 中有但 Web 中没有的指标（可能为 PDF 独有）
    pdf_only_labels = set(pdf_groups.keys()) - set(web_groups.keys())
    for label in pdf_only_labels:
        for item in pdf_groups[label]:
            conflicts.append({
                "label": label,
                "pdf_value": item["value"],
                "pdf_unit": item.get("unit", ""),
                "pdf_context": item.get("context", ""),
                "web_value": "",
                "web_unit": "",
                "web_context": "",
                "status": "pdf_only",
                "diff_ratio": 0.0,
            })

    # 检测 Web 中有但 PDF 中没有的指标
    web_only_labels = set(web_groups.keys()) - set(pdf_groups.keys())
    for label in web_only_labels:
        for item in web_groups[label]:
            conflicts.append({
                "label": label,
                "pdf_value": "",
                "pdf_unit": "",
                "pdf_context": "",
                "web_value": item["value"],
                "web_unit": item.get("unit", ""),
                "web_context": item.get("context", ""),
                "status": "web_only",
                "diff_ratio": 0.0,
            })

    return conflicts


def data_conflict_checker_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    轻量化多源数据冲突检测节点。

    在检索完成后、分析节点之前执行，纯文本正则提取数值，
    对比 PDF 和 Web 来源，标记冲突。

    不在 state 中修改任何检索结果，只新增 data_conflicts 字段。
    """
    top_k_chunks = state.get("top_k_chunks", [])
    logger.info("🔎 [数据冲突检测] 开始检查多源数据一致性...")
    logger.info(f"   素材总数: {len(top_k_chunks)} 条")

    # 分离 PDF 和 Web 素材
    pdf_materials = [c for c in top_k_chunks if c.get("source_type") == "pdf"]
    web_materials = [c for c in top_k_chunks if c.get("source_type") == "web"]

    logger.info(f"   PDF: {len(pdf_materials)} 条, Web: {len(web_materials)} 条")

    # 如果只有单一来源，直接返回
    if not pdf_materials or not web_materials:
        logger.info("   ✅ 仅单一来源，无需冲突检测")
        return {
            "data_conflicts": [],
            "data_conflict_detected": False,
            "data_conflict_count": 0,
        }

    # 提取数值
    pdf_values = []
    for m in pdf_materials:
        pdf_values.extend(extract_quantities(m.get("text", "")))

    web_values = []
    for m in web_materials:
        web_values.extend(extract_quantities(m.get("text", "")))

    logger.info(f"   PDF 提取 {len(pdf_values)} 个量化指标, Web 提取 {len(web_values)} 个量化指标")

    if not pdf_values or not web_values:
        logger.info("   ✅ 无重叠量化指标，无需冲突检测")
        return {
            "data_conflicts": [],
            "data_conflict_detected": False,
            "data_conflict_count": 0,
        }

    # 对比数值
    comparisons = _compare_values(pdf_values, web_values, pdf_materials, web_materials)

    # 统计冲突
    conflicts = [c for c in comparisons if c.get("status") == "conflict"]
    consistents = [c for c in comparisons if c.get("status") == "consistent"]

    # 生成冲突警告文本（供下游写入报告）
    conflict_warnings = []
    for c in conflicts:
        warning = (
            f"🔴【数据冲突】{c['label']}\n"
            f"  📄 内部文档: {c['pdf_value']}{c['pdf_unit']} (来源: {c.get('pdf_source', '内部文档')})\n"
            f"  🌐 公开网络: {c['web_value']}{c['web_unit']} (来源: {c.get('web_source', '公开网络')})\n"
            f"  ⚠️ 差异率: {c['diff_ratio'] * 100:.1f}%\n"
            f"  请人工核实后确定最终数值。"
        )
        conflict_warnings.append(warning)
        logger.warning(f"   🔴 冲突: {c['label']} | "
                       f"PDF={c['pdf_value']}{c['pdf_unit']} vs "
                       f"Web={c['web_value']}{c['web_unit']} "
                       f"(差异{c['diff_ratio'] * 100:.1f}%)")

    for c in consistents:
        logger.info(f"   🟢 一致: {c['label']} | "
                    f"PDF={c['pdf_value']}{c['pdf_unit']} vs "
                    f"Web={c['web_value']}{c['web_unit']}")

    # 统计
    total_conflicts = len(conflicts)
    total_consistent = len(consistents)
    pdf_only_count = len([c for c in comparisons if c.get("status") == "pdf_only"])
    web_only_count = len([c for c in comparisons if c.get("status") == "web_only"])

    logger.info(f"   📊 检测结果: "
                f"一致={total_consistent}, 冲突={total_conflicts}, "
                f"仅PDF={pdf_only_count}, 仅Web={web_only_count}")

    return {
        "data_conflicts": comparisons,
        "data_conflict_detected": total_conflicts > 0,
        "data_conflict_count": total_conflicts,
        "data_conflict_warnings": conflict_warnings,
        "data_conflict_flag": total_conflicts > 0,  # 供下游路由判断
    }