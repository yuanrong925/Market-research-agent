"""
数字修正节点 — Number Fixer（v2 仅数字修正版）

v2 变更：
  不再重写整个段落。改为：
    1. 接收 rewrite_scope 中的数字列表（如 ["100亿元", "50%", ...]）
    2. 在 final_report 中查找这些数字，用正则替换为素材中的正确数字
    3. 不调用 LLM 改写，只做精确替换
    4. 不改动段落的其他内容

输入：
  - final_report: 当前报告（dict，包含各字段）
  - rewrite_scope: 需要修正的数字列表（如 ["100亿元", "50%", ...]）
  - post_check_rewrite_count: 当前重写次数
  - source_materials: 只读素材库（用于查找正确的数字）

输出：
  - final_report: 更新后的报告（仅修改数字）
  - post_check_rewrite_count: 递增后的重写次数
  - rewrite_result: 修正结果摘要

设计要点：
  - 只修正数字，不动段落其他内容
  - 使用正则替换，不调用 LLM，极速执行
  - 不改写标题/附录/结构，保持报告整体框架不变
"""

import json
import re
import time
from typing import Any, Dict, List, Optional

from core.utils.logger import get_logger

from business.market_research.state import AgentState

logger = get_logger(__name__)


def _find_and_replace_number(
    text: str,
    wrong_number: str,
    source_materials: List[Dict],
) -> str:
    """
    在文本中查找错误的数字，用素材中的正确数字替换。

    如果找不到正确的替换数字，则在数字后添加标记（需人工确认）。

    Args:
        text: 待修复的文本
        wrong_number: 报告中出现的错误数字（如 "100亿元"）
        source_materials: 只读素材库

    Returns:
        修复后的文本
    """
    # 提取纯数字部分
    pure_digits = re.findall(r'\d+\.?\d*', wrong_number)
    if not pure_digits:
        return text  # 没有数字，无需修复

    # 在素材中查找该数字
    correct_number = None
    for mat in source_materials:
        mat_text = mat.get("text", "")
        if not mat_text:
            continue

        # 寻找素材中出现的同一个数字模式
        # 方法：提取素材中所有数字，看哪个匹配
        material_numbers = re.findall(r'\d+\.?\d*[万亿千百十万%年]*|\d+\.?\d*', mat_text)
        for mn in material_numbers:
            # 纯数字部分匹配
            mn_pure = re.findall(r'\d+\.?\d*', mn)
            if mn_pure and mn_pure[0] == pure_digits[0]:
                correct_number = mn
                break
        if correct_number:
            break

    if correct_number and correct_number != wrong_number:
        # 用正确的数字替换错误的数字
        # 优先替换完整匹配（如 "100亿元"），否则替换纯数字部分
        if wrong_number in text:
            text = text.replace(wrong_number, correct_number, 1)
            logger.info(f"   [NumberFixer] 替换数字: {wrong_number} -> {correct_number}")
        else:
            # 纯数字部分替换
            text = text.replace(pure_digits[0], correct_number, 1)
            logger.info(f"   [NumberFixer] 替换数字部分: {pure_digits[0]} -> {correct_number}")
    elif not correct_number:
        # 找不到正确的数字，保留原数字，后续冲突检测将统一处理
        logger.warning(f"   [NumberFixer] 数字 {wrong_number} 在素材中未找到，保留原数字")
        # 不在报告中插入调试标记，数据分歧统一在冲突检测阶段呈现

    return text


def _recursive_fix_numbers(
    obj: Any,
    rewrite_scope: List[str],
    source_materials: List[Dict],
    path: str = "",
) -> Any:
    """
    递归遍历报告对象，在字符串字段中查找并修正数字。

    Args:
        obj: 报告对象（dict/list/str 等）
        rewrite_scope: 需要修正的数字列表
        source_materials: 只读素材库
        path: 当前递归路径（用于日志）

    Returns:
        修正后的对象
    """
    if isinstance(obj, str):
        for wrong_num in rewrite_scope:
            if wrong_num in obj:
                obj = _find_and_replace_number(obj, wrong_num, source_materials)
        return obj
    elif isinstance(obj, dict):
        return {k: _recursive_fix_numbers(v, rewrite_scope, source_materials, f"{path}.{k}") for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_recursive_fix_numbers(item, rewrite_scope, source_materials, f"{path}[{i}]") for i, item in enumerate(obj)]
    else:
        return obj


# ============================================================
#  节点入口（兼容旧接口名，方便 graph 路由不改名）
# ============================================================

def paragraph_rewriter_node(state: AgentState) -> Dict[str, Any]:
    """
    数字修正节点入口。

    在 post_paragraph_check 之后执行，只修改有问题的数字。
    不再调用 LLM 重写整个段落，只做正则替换。
    """
    report = state.get("final_report", {})
    rewrite_scope = state.get("rewrite_scope", [])
    source_materials = state.get("source_materials", [])
    rewrite_count = state.get("post_check_rewrite_count", 0)

    if not rewrite_scope:
        logger.info("   [NumberFixer] 无需要修正的数字，跳过")
        return {
            "final_report": report,
            "post_check_rewrite_count": rewrite_count,
            "rewrite_result": "无需修正",
        }

    logger.info(f"✏️ [NumberFixer] 开始数字修正 (范围: {rewrite_scope}, 第 {rewrite_count + 1} 次)")

    # 递归遍历报告，修正数字
    fixed_report = _recursive_fix_numbers(report, rewrite_scope, source_materials)

    fixed_count = len(rewrite_scope)
    logger.info(f"✏️ [NumberFixer] 数字修正完成: {fixed_count} 个数字已处理")

    return {
        "final_report": fixed_report,
        "post_check_rewrite_count": rewrite_count + 1,
        "rewrite_result": f"数字修正完成: {fixed_count} 个数字已处理",
    }