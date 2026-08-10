"""
后置段落校验节点 — Post Paragraph Check（v3 仅数字校验版）

v3 变更（仅数字校验）：
  1. 只提取数字/数据/百分比/年份，不再提取核心结论和来源引用
  2. 只校验数字在 source_materials 中是否有支撑
  3. 有问题只改数字（不重写整个段落）
  4. 移除所有非数字关键事实的提取和比对逻辑
  5. 节点总耗时目标：< 5s

设计要点：
  - 纯正则提取数字（不再调用 LLM）
  - 提取数字后，拿着数字和 source_materials 做比对
  - 比对阶段使用规则匹配（数字是否在素材中出现）
  - 比对结果：ok / 数字有误
  - 最多 2 轮重写
"""

import json
import re
import time
from typing import Any, Dict, List

from core.utils.logger import get_logger

from business.market_research.state import AgentState

logger = get_logger(__name__)


# ============================================================
#  最大重写轮次
# ============================================================

# 最大重写轮次（改为1次，因为>30%才修正，且只修正1次）
_POST_CHECK_MAX_REWRITE = 1


# ============================================================
#  v3: 纯正则提取数字（不再调用LLM）
# ============================================================

_NUMBER_PATTERN = re.compile(
    r'\d{1,3}(?:,\d{3})*(?:\.\d+)?[万亿千百十万]*[亿万千百十]*'
    r'|\d+\.?\d*[万亿千百十万%年元美元欧元日元英镑]?'
    r'|\d+\.?\d*'
)


def _extract_numbers_by_regex(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    纯正则提取报告中的所有数字，不再调用 LLM。

    从报告的所有文本字段中提取数字，去重后返回。
    耗时预计 < 0.1s。

    Args:
        report: 完整报告（Writer 输出）

    Returns:
        {"numbers": [{"number": "100亿元", "context": "...", "section": ""}], "total_numbers": N}
    """
    # 将报告展平为文本
    report_str = json.dumps(report, ensure_ascii=False, indent=2)

    # 提取所有匹配的数字
    matches = _NUMBER_PATTERN.findall(report_str)

    # 过滤掉过短或过于常见的数字
    filtered = []
    seen = set()
    for m in matches:
        m = m.strip()
        if not m:
            continue
        # 去重
        if m in seen:
            continue
        seen.add(m)

        # 过滤掉纯单个数字（如 1, 2, 3 等，但保留 2024, 100 等）
        pure_digits = re.sub(r'[^\d.]', '', m)
        if pure_digits:
            try:
                val = float(pure_digits)
                if val < 10 and len(m) <= 2:
                    continue
            except ValueError:
                pass

        filtered.append(m)

    # 去重后构建结果
    unique_numbers = list(dict.fromkeys(filtered))

    numbers = []
    for num in unique_numbers:
        # 找到该数字在报告中的上下文（简单截取前后文字）
        idx = report_str.find(num)
        context = ""
        if idx >= 0:
            start = max(0, idx - 15)
            end = min(len(report_str), idx + len(num) + 15)
            context = report_str[start:end].replace('\n', ' ').strip()
            if len(context) > 40:
                context = context[:40] + '...'

        numbers.append({
            "number": num,
            "context": context,
            "section": "",
        })

    logger.info(f"   [PostCheck] 正则提取数字: {len(numbers)} 个 (去重后)")

    return {
        "numbers": numbers,
        "total_numbers": len(numbers),
    }


# ============================================================
#  v2: 简单文本/规则比对（不再调 LLM）
# ============================================================

def _check_number_against_source(number_item: Dict[str, str], source_materials: List[Dict]) -> Dict[str, Any]:
    """
    检查单个数字是否在 source_materials 中有支撑。

    使用简单文本匹配规则，不再调 LLM。

    Args:
        number_item: {"number": "100亿元", "context": "...", "section": "..."}
        source_materials: 只读素材库

    Returns:
        {{
          "number": "100亿元",
          "context": "...",
          "found": bool,  # True = 在素材中找到该数字
          "confidence": float,  # 0.0~1.0
          "detail": str,  # 匹配详情
        }}
    """
    number_str = number_item.get("number", "")
    context = number_item.get("context", "")

    if not number_str:
        return {
            "number": number_str,
            "context": context,
            "found": True,  # 没有数字视为通过
            "confidence": 1.0,
            "detail": "无数字，跳过",
        }

    # 提取纯数字部分（去掉单位、百分号等）
    pure_digits = re.findall(r'\d+\.?\d*', number_str)
    # 提取带单位的数字（如"100亿元"、"50%"等）
    number_with_unit = number_str.strip()

    best_score = 0.0
    best_detail = ""

    for i, mat in enumerate(source_materials):
        mat_text = mat.get("text", "")
        if not mat_text:
            continue

        # 匹配规则 1：完整数字字符串在素材中出现
        if number_with_unit in mat_text:
            best_score = 1.0
            best_detail = f"素材[{i}] 直接匹配数字「{number_with_unit}」"
            break

        # 匹配规则 2：纯数字部分匹配
        if pure_digits:
            matched_digits = 0
            for d in pure_digits:
                if d in mat_text:
                    matched_digits += 1
            if matched_digits > 0:
                score = matched_digits / len(pure_digits)
                if score > best_score:
                    best_score = score
                    best_detail = f"素材[{i}] 匹配 {matched_digits}/{len(pure_digits)} 个数字部分"

    found = best_score > 0.5

    return {
        "number": number_str,
        "context": context,
        "found": found,
        "confidence": round(best_score, 4),
        "detail": best_detail if best_detail else "数字在素材中未找到",
    }


def _aggregate_number_check_results(
    check_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    汇总所有数字的校验结果。

    Returns:
        {{
          "post_check_passed": bool,
          "has_issues": bool,
          "rewrite_scope": List[str],  # 需要修正的数字列表
          "summary": str,
          "check_results": List[Dict],
        }}
    """
    if not check_results:
        return {
            "post_check_passed": True,
            "has_issues": False,
            "rewrite_scope": [],
            "summary": "无数字需要校验",
            "check_results": [],
        }

    total = len(check_results)
    found_count = sum(1 for r in check_results if r["found"])
    not_found = [r for r in check_results if not r["found"]]

    has_issues = len(not_found) > 0

    # 构建需要修正的数字列表
    rewrite_scope = []
    for r in not_found:
        num = r.get("number", "")
        if num:
            rewrite_scope.append(num)

    summary_parts = []
    summary_parts.append(f"{total} 个数字")
    summary_parts.append(f"{found_count} 个有素材支撑")
    if not_found:
        summary_parts.append(f"{len(not_found)} 个无支撑")
    summary = ", ".join(summary_parts)

    post_check_passed = not has_issues

    logger.info(f"   [PostCheck] 数字汇总: {summary}")
    if has_issues:
        logger.warning(f"   [PostCheck] 发现 {len(not_found)} 个数字无素材支撑")

    return {
        "post_check_passed": post_check_passed,
        "has_issues": has_issues,
        "rewrite_scope": rewrite_scope,
        "summary": summary,
        "check_results": check_results,
    }


# ============================================================
#  v3 节点入口：正则提取 + 规则比对
# ============================================================

def post_paragraph_check_node(state: AgentState) -> Dict[str, Any]:
    """
    后置段落校验节点 v3（仅数字校验版）。

    彻底移除逐段调 LLM 的循环逻辑，以及非数字关键事实的提取和比对。
    改为：
      1. 纯正则提取数字（不再调用LLM）
      2. 做简单文本/规则比对（数字是否在素材中出现）
      3. 最多重写 1 轮（仅修正数字，不重写段落）
      4. 节点总超时 20s 封顶

    输入依赖：
      - final_report: Writer 生成的报告
      - source_materials: 只读素材库
      - post_check_rewrite_count: 当前重写次数（首次为 0）

    输出：
      - post_check_passed: 是否全部通过
      - post_check_rewrite_count: 更新后的重写次数
      - post_check_meltdown: 是否熔断
      - rewrite_scope: 需要修正的数字列表
    """
    report = state.get("final_report", {})
    source_materials = state.get("source_materials", [])
    rewrite_count = state.get("post_check_rewrite_count", 0)

    logger.info(f"🔍 [PostCheck] v3 开始后置数字校验 (重写次数: {rewrite_count})...")
    start_time = time.time()

    # 检查报告是否有效 — 不再依赖"标题"键，检查是否有实质文本内容
    if not report:
        logger.warning("   [PostCheck] 报告为空，跳过校验")
        return {
            "post_check_passed": True,
            "post_check_results": [],
            "post_check_rewrite_count": rewrite_count,
            "post_check_meltdown": False,
            "rewrite_scope": [],
        }

    report_str = json.dumps(report, ensure_ascii=False)
    # 少于 20 个有效字符就算无效报告
    if len(report_str.strip()) < 20 or report_str == "{}":
        logger.warning(f"   [PostCheck] 报告内容过短({len(report_str)}字符)，视为无效，跳过校验")
        return {
            "post_check_passed": True,
            "post_check_results": [],
            "post_check_rewrite_count": rewrite_count,
            "post_check_meltdown": False,
            "rewrite_scope": [],
        }

    # 1. 纯正则提取所有数字（不再调用LLM）
    extracted = _extract_numbers_by_regex(report)
    numbers = extracted.get("numbers", [])
    total_numbers = extracted.get("total_numbers", 0)
    logger.info(f"   [PostCheck] 正则提取数字: {total_numbers} 个")

    if not numbers:
        logger.info("   [PostCheck] 无数字，标记为通过")
        return {
            "post_check_passed": True,
            "post_check_results": [],
            "post_check_rewrite_count": rewrite_count,
            "post_check_meltdown": False,
            "rewrite_scope": [],
        }

    # 2. 对每个数字做规则比对（不再调 LLM）
    check_results = []
    for num_item in numbers:
        result = _check_number_against_source(num_item, source_materials)
        check_results.append(result)

    # 3. 汇总结果
    aggregated = _aggregate_number_check_results(check_results)
    elapsed = time.time() - start_time
    logger.info(f"   [PostCheck] 数字校验完成: {aggregated['summary']}, 耗时: {elapsed:.2f}s")

    # ===== 【新增】计算问题比例 =====
    total_numbers = len(check_results)
    issue_count = sum(1 for r in check_results if not r.get("found", True))
    issue_ratio = (issue_count / max(total_numbers, 1)) * 100  # 百分比
    logger.info(f"   [PostCheck] 数字问题比例: {issue_count}/{total_numbers} = {issue_ratio:.1f}%")

    # 按照您的需求：
    #   > 30% → 自动修正（只改数字，最多1次）
    #   ≤ 30% → 直接输出，返回用户人工选择
    if issue_ratio > 30 and aggregated.get("has_issues", False):
        logger.info(f"   [PostCheck] 问题比例 {issue_ratio:.1f}% > 30%，进入自动修正")
    elif aggregated.get("has_issues", False):
        logger.info(f"   [PostCheck] 问题比例 {issue_ratio:.1f}% ≤ 30%，直接输出，需人工确认")
    # ================================

    # 4. 更新重写次数和熔断
    new_rewrite_count = rewrite_count + 1 if aggregated.get("has_issues", False) else rewrite_count
    meltdown = new_rewrite_count >= _POST_CHECK_MAX_REWRITE and aggregated.get("has_issues", False)

    if meltdown:
        logger.warning(f"   [PostCheck] 熔断触发: 重写次数已达 {new_rewrite_count} 次，输出最终报告")

    return {
        "post_check_passed": aggregated.get("post_check_passed", True),
        "post_check_results": aggregated.get("check_results", []),
        "post_check_rewrite_count": new_rewrite_count,
        "post_check_meltdown": meltdown,
        "rewrite_scope": aggregated.get("rewrite_scope", []),
        # ===== 【新增】输出问题比例，供路由决策 =====
        "post_check_issue_ratio": round(issue_ratio, 1),
        "post_check_total_numbers": total_numbers,
        "post_check_issue_count": issue_count,
        # ===========================================
    }         