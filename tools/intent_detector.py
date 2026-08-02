"""
意图识别前置兜底模块

检测用户提问是否为「概括、总结、解读上传PDF内容」类意图。
当检测命中时，强制锁定为仅PDF模式，阻断联网搜索。
"""

import re
from typing import Dict, Optional

# 文档解读/总结类意图关键词（按优先级从高到低排列）
DOCUMENT_SUMMARY_KEYWORDS = [
    # 总结类
    "总结全文",
    "总结文档",
    "总结报告",
    "总结内容",
    "概括全文",
    "概括文档",
    "概括内容",
    "概述全文",
    "概述文档",
    "概述内容",
    "文档大意",
    "文章大意",
    "全文大意",
    "内容摘要",
    "内容总结",
    # 解读类
    "解读这份文件",
    "解读文档",
    "解读报告",
    "解读一下",
    # 含义类
    "文章讲了什么",
    "文档讲了什么",
    "报告讲了什么",
    "这篇文章说什么",
    "这份文件说什么",
    "主要内容是什么",
    # 梳理类
    "梳理文档观点",
    "梳理观点",
    "梳理内容",
    "梳理全文",
    # 简单
    "讲什么",
    "说的什么",
    "什么内容",
    "核心观点",
    "核心内容",
    "主要观点",
    "主要论述",
    "主题思想",
    "中心思想",
]

# 模糊匹配关键词（用于短句中的部分匹配）
FUZZY_PATTERNS = [
    re.compile(r'总结.*(?:全文|文档|报告|内容|PDF|文件|这篇)'),
    re.compile(r'概括.*(?:全文|文档|报告|内容|PDF|文件|这篇)'),
    re.compile(r'概述.*(?:全文|文档|报告|内容|PDF|文件|这篇)'),
    re.compile(r'解读.*(?:文件|文档|报告|PDF|内容|这篇)'),
    re.compile(r'(?:全文|整篇|文档|报告).*(?:总结|概括|概述|大意|要点)'),
    re.compile(r'(?:讲|说|介绍).*(?:什么|哪些|内容|要点)'),
]


def detect_document_summary_intent(task: str, has_pdf: bool) -> Dict:
    """
    检测用户提问是否为文档解读/总结类意图。

    参数:
        task: 用户提问文本
        has_pdf: 是否已上传PDF文件

    返回:
        {
            "is_summary_intent": bool,  # 是否命中总结类意图
            "matched_keyword": str,      # 命中的关键词（用于日志）
            "confidence": float,         # 0.0-1.0 置信度
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
        # 以"这"、"该"、"这个"等开头且长度短的句子，很可能是针对文档的提问
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

    返回:
        {
            "override": bool,            # 是否覆盖
            "new_mode": str,             # 覆盖后的模式 (disabled/auto/enabled)
            "notification": str,         # 推送给前端的通知消息
            "matched_keyword": str,      # 命中的关键词
        }
    """
    intent = detect_document_summary_intent(task, has_pdf)

    if not intent["is_summary_intent"]:
        return {
            "override": False,
            "new_mode": current_mode,
            "notification": "",
            "matched_keyword": "",
        }

    # 命中总结意图 → 强制锁定为仅PDF模式
    return {
        "override": True,
        "new_mode": "disabled",  # 强制锁定为仅PDF
        "notification": "检测到您需要解读上传文档内容，本次仅基于 PDF 生成结果，不使用网络信息",
        "matched_keyword": intent["matched_keyword"],
    }