"""
意图识别前置兜底模块

规则2：用户输入意图智能识别校验（全局前置，优先级仅次于用户手动模式）

触发关键词集合：
  总结文件、概述文档、基于本文件、根据PDF内容、文档内信息、梳理文件内容、针对这份材料

分级处理优先级：用户手动选择模式 > 意图识别提醒
  1. 用户手动选中【仅PDF】：命中关键词无任何弹窗，直接进入工作流程；
  2. 用户手动选中【PDF+联网】：弹出二选一提示框；
  3. 用户选中【纯联网】：存在PDF时前端已拦截，无需额外处理。
"""

import re
from typing import Dict

# ============================================================
#  规则2：触发关键词集合（共6个指定关键词）
# ============================================================
DOCUMENT_SUMMARY_KEYWORDS = [
    # 规则2指定关键词（6个）
    "总结文件",
    "概述文档",
    "基于本文件",
    "根据PDF内容", "根据 PDF 内容",
    "文档内信息",
    "梳理文件内容",
    "针对这份材料",
    # 原有关键词（保留兼容）
    "总结全文", "总结文档", "总结报告", "总结内容",
    "概括全文", "概括文档", "概括内容",
    "概述全文", "概述内容",
    "文档大意", "文章大意", "全文大意",
    "内容摘要", "内容总结",
    "解读这份文件", "解读文档", "解读报告", "解读一下",
    "文章讲了什么", "文档讲了什么", "报告讲了什么",
    "这篇文章说什么", "这份文件说什么", "主要内容是什么",
    "梳理文档观点", "梳理观点", "梳理内容", "梳理全文",
    "讲什么", "说的什么", "什么内容",
    "核心观点", "核心内容", "主要观点",
    "主要论述", "主题思想", "中心思想",
]

FUZZY_PATTERNS = [
    re.compile(r'总结.*(?:全文|文档|报告|内容|PDF|文件|这篇|材料)'),
    re.compile(r'概括.*(?:全文|文档|报告|内容|PDF|文件|这篇|材料)'),
    re.compile(r'概述.*(?:全文|文档|报告|内容|PDF|文件|这篇|材料)'),
    re.compile(r'解读.*(?:文件|文档|报告|PDF|内容|这篇|材料)'),
    re.compile(r'(?:全文|整篇|文档|报告|这份材料).*(?:总结|概括|概述|大意|要点)'),
    re.compile(r'(?:讲|说|介绍).*(?:什么|哪些|内容|要点)'),
    re.compile(r'基于.*(?:本文件|PDF|文档|报告|材料)'),
    re.compile(r'根据.*(?:PDF|文档|文件|报告|材料).*内容'),
    re.compile(r'梳理.*(?:文件|文档|PDF|报告|材料).*内容'),
    re.compile(r'针对.*(?:这份|该|这个).*(?:材料|文件|文档|报告|PDF)'),
]


def detect_document_summary_intent(task: str, has_pdf: bool) -> Dict:
    """
    检测用户提问是否为文档解读/总结类意图。

    参数:
        task: 用户提问文本
        has_pdf: 是否已上传PDF文件

    返回:
        {
            "is_summary_intent": bool,
            "matched_keyword": str,
            "confidence": float,
        }
    """
    if not task or not task.strip():
        return {"is_summary_intent": False, "matched_keyword": "", "confidence": 0.0}

    task_lower = task.strip()
    result = {"is_summary_intent": False, "matched_keyword": "", "confidence": 0.0}

    # 1. 精确关键词匹配（最高优先级）
    for keyword in DOCUMENT_SUMMARY_KEYWORDS:
        if keyword in task_lower:
            result["is_summary_intent"] = True
            result["matched_keyword"] = keyword
            result["confidence"] = 0.95
            return result

    # 2. 正则模糊匹配（中等优先级）
    for pattern in FUZZY_PATTERNS:
        if pattern.search(task_lower):
            result["is_summary_intent"] = True
            result["matched_keyword"] = f"模糊匹配: {pattern.pattern}"
            result["confidence"] = 0.7
            return result

    # 3. 短句场景检测（低优先级，仅当有PDF时）
    if has_pdf and len(task_lower) <= 20:
        short_indicators = [
            "这", "该", "这个", "这个文件", "这份文件", "这篇文章", "这份报告",
            "这个PDF", "这个文档", "该文档", "该文件", "该报告",
        ]
        for indicator in short_indicators:
            if task_lower.startswith(indicator) or indicator in task_lower:
                result["is_summary_intent"] = True
                result["matched_keyword"] = f"短句场景: {indicator}"
                result["confidence"] = 0.5
                return result

    return result


def get_override_mode_from_intent(task: str, has_pdf: bool, current_mode: str) -> Dict:
    """
    根据意图检测结果，决定是否覆盖搜索模式。

    规则2 分级处理优先级：用户手动选择模式 > 意图识别提醒
      1. 用户手动选中【仅PDF】（current_mode=disabled/pdf_only）：
         命中关键词无任何弹窗，直接进入工作流程，不 override；
      2. 用户手动选中【PDF+联网】（current_mode=auto/pdf_web）：
         弹出二选一提示框，由前端决定是否切换；
      3. 用户选中【纯联网】（current_mode=enabled/web_only）：
         存在PDF时前端已拦截，无需额外处理。

    返回:
        {
            "override": bool,          # 是否强制覆盖模式
            "new_mode": str,            # 建议的新模式
            "notification": str,        # 提示文案
            "matched_keyword": str,     # 命中的关键词
            "suggest_switch": bool,     # 是否建议切换（前端据此弹二选一）
        }
    """
    # 标准化 current_mode
    mode = current_mode.lower()
    if mode in ("disabled", "pdf_only"):
        user_mode = "pdf_only"
    elif mode in ("enabled", "web_only"):
        user_mode = "web_only"
    else:
        user_mode = "pdf_web"  # auto / pdf_web 默认

    intent = detect_document_summary_intent(task, has_pdf)

    if not intent["is_summary_intent"]:
        return {
            "override": False,
            "new_mode": current_mode,
            "notification": "",
            "matched_keyword": "",
            "suggest_switch": False,
        }

    # 规则2-1：用户手动选中【仅PDF】→ 无任何弹窗，直接进入
    if user_mode == "pdf_only":
        return {
            "override": False,  # 不 override，保持现有模式
            "new_mode": current_mode,
            "notification": "",
            "matched_keyword": intent["matched_keyword"],
            "suggest_switch": False,  # 前端不弹窗
        }

    # 规则2-3：用户手动选中【纯联网】→ 前端已拦截，无需处理
    if user_mode == "web_only":
        return {
            "override": False,
            "new_mode": current_mode,
            "notification": "",
            "matched_keyword": intent["matched_keyword"],
            "suggest_switch": False,
        }

    # 规则2-2：用户手动选中【PDF+联网】→ 弹出二选一提示框
    # 返回建议切换，由前端决定是否确认切换
    return {
        "override": False,  # 不强制覆盖，只建议
        "new_mode": "disabled",  # 建议切换为仅PDF模式
        "notification": "检测到您需求偏向仅基于文档内容分析，是否切换至【仅PDF】模式（关闭联网，仅使用文档信息）？",
        "matched_keyword": intent["matched_keyword"],
        "suggest_switch": True,  # 前端据此弹出二选一
    }