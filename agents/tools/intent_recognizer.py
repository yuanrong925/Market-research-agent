"""
agents/intent_recognizer.py — 任务意图识别系统

第一优先级：在检索流程最开头解析用户输入任务文本，优先级高于环境变量、检索分数、覆盖率等所有判断。

意图分类：
  1. DOCUMENT_LOCAL（文档本地类）— 强制关闭联网，跳过所有充足度校验
  2. FULL_SUMMARY（全文总结类）— 抛弃条数/覆盖率/相似度限制
  3. PRECISE_QA（精准问答类）— 取消最小条数硬性要求，用双重指标判定
  4. EXPANSION_RESEARCH（拓展调研类）— 保留原有混合逻辑
  5. EXPLICIT_PDF_ONLY（显式约束类）— 强制纯 PDF 模式
"""

import re
from typing import Dict, List, Optional, Tuple

# ============================================================
#  意图关键词匹配规则
# ============================================================

# ——— 文档本地类意图（强制关闭联网，跳过所有充足度校验） ———
DOCUMENT_LOCAL_PATTERNS = [
    r"总结\s*(PDF|文件|文档|全文|报告|资料)",
    r"概括\s*(PDF|文件|文档|全文|报告|资料)",
    r"提取\s*(PDF|文件|文档|全文|报告|资料)",
    r"梳理\s*(PDF|报告|文件|文档|资料)",
    r"翻译\s*(PDF|文件|文档)",
    r"全文\s*(总结|概括|摘要|翻译)",
    r"总结\s*[这那].*PDF",
    r"PDF\s*总结",
    r"概括全文",
    r"提取全文",
    r"梳理报告",
    r"翻译\s*PDF",
    r"总结.*文件",
    r"总结.*文档",
]

# ——— 全文总结类任务 ———
FULL_SUMMARY_PATTERNS = [
    r"总结\s*(PDF|文件|文档|全文|报告|资料|文章)",
    r"概括\s*(PDF|文件|文档|全文|报告|资料|文章)",
    r"提取\s*(全文|全部内容|所有内容)",
    r"全文\s*(总结|概括|摘要|翻译)",
    r"梳理\s*(报告|文件|文档|全文)",
    r"总结.*全文",
    r"概括.*全文",
    r"提取.*内容",
    r"写出.*摘要",
    r"生成.*摘要",
    r"摘要.*PDF",
    r"摘要.*文件",
    r"摘要.*文档",
]

# ——— 精准问答 / 提取指定数据任务 ———
PRECISE_QA_PATTERNS = [
    r"查\s*(一下|找|看|询)?\s*(数字|数据|统计|指标|参数)",
    r"找\s*(出|到)?\s*(数据|数字|信息|资料|内容|观点|论据)",
    r"提取\s*(数据|信息|数字|指标|参数|内容)",
    r"定向\s*(提问|查询|查找|检索)",
    r"具体\s*(数据|数字|信息|内容|指标|参数)",
    r"精准\s*(查询|查找|检索|提问)",
    r"查询\s*(数据|信息|数字|指标|参数)",
    r"告诉\s*我.*(数据|数字|信息|指标|参数)",
    r"多少|多久|多远|多高|多大|多长",
    r"什么\s*(是|叫|称)",
    r"是否|是否.*有",
    r"列出.*(数据|信息|内容|观点|要素)",
    r"数字.*(多少|是|为)",
    r"占比|比例|率$|增长率|渗透率|市场份额",
]

# ——— 拓展调研类意图 ———
EXPANSION_RESEARCH_PATTERNS = [
    r"最新\s*(行业|市场|数据|动态|趋势|报告|新闻)",
    r"行业\s*(数据|报告|分析|动态|趋势|现状)",
    r"市场\s*(预测|趋势|分析|报告|数据|动态)",
    r"竞品\s*(对比|分析|比较|情况|信息)",
    r"竞争\s*(格局|分析|对比|情况)",
    r"海外\s*(政策|市场|动态|趋势|情况|信息)",
    r"补充\s*(外部|额外|更多|其他)\s*(信息|资料|数据)",
    r"外部\s*(信息|数据|资料|来源)",
    r"最新\s*(动态|进展|情况|消息)",
    r"全球\s*(市场|趋势|数据|报告|情况)",
    r"国际\s*(市场|趋势|数据|报告|情况)",
    r"宏观\s*(经济|环境|趋势|数据|分析)",
    r"对标\s*(分析|公司|企业|案例)",
    r"行业\s*(调研|研究|调查)",
]

# ——— 显式约束指令（禁止联网） ———
EXPLICIT_PDF_ONLY_PATTERNS = [
    r"禁止\s*联网",
    r"仅[用使].*PDF\s*(原文|内容|信息|资料)",
    r"不要.*(联网|网页|网络|搜索|外部)",
    r"无需.*(联网|搜索|网络)",
    r"纯\s*PDF\s*(模式|检索|分析)",
    r"仅(基于|使用|根据|依靠)\s*PDF",
    r"不离线|不联网|不搜索|不查网",
    r"只用.*原文",
    r"只.*PDF",
    r"PDF.*原文",
    r"不要.*外部.*(信息|数据|网页|网络)",
    r"仅.*(本地|内部|已有|上传)",
]

# ============================================================
#  意图枚举
# ============================================================

class TaskIntent:
    """任务意图枚举"""
    DOCUMENT_LOCAL = "document_local"       # 文档本地类（全文总结）
    FULL_SUMMARY = "full_summary"           # 全文总结类
    PRECISE_QA = "precise_qa"              # 精准问答类
    EXPANSION_RESEARCH = "expansion_research"  # 拓展调研类
    GENERAL = "general"                     # 通用/未分类

    # 显式约束是附加标志，不是独立意图
    EXPLICIT_PDF_ONLY = "explicit_pdf_only"


# ============================================================
#  意图识别主函数
# ============================================================

def recognize_intent(task: str) -> Dict[str, any]:
    """
    识别用户任务意图。

    返回:
      {
        "intent": TaskIntent 枚举值,
        "explicit_pdf_only": bool,   # 是否包含显式禁用联网约束
        "matched_pattern": str,      # 匹配到的第一个关键词模式
        "confidence": float,         # 置信度 0.0-1.0
      }
    """
    if not task or not task.strip():
        return {
            "intent": TaskIntent.GENERAL,
            "explicit_pdf_only": False,
            "matched_pattern": "",
            "confidence": 1.0,
        }

    task_lower = task.lower().strip()

    # ===== 第一优先级：显式约束指令 =====
    for pattern in EXPLICIT_PDF_ONLY_PATTERNS:
        if re.search(pattern, task_lower):
            # 继续检查具体意图
            break
    # 深度检查显式约束
    explicit_pdf_only = False
    for pattern in EXPLICIT_PDF_ONLY_PATTERNS:
        if re.search(pattern, task_lower):
            explicit_pdf_only = True
            break

    # ===== 第二优先级：文档本地类（全文总结特定文档） =====
    # 匹配优先级最高，因为这类任务需要完全跳过联网和充足度校验
    for pattern in DOCUMENT_LOCAL_PATTERNS:
        match = re.search(pattern, task_lower)
        if match:
            return {
                "intent": TaskIntent.DOCUMENT_LOCAL,
                "explicit_pdf_only": True,  # 文档本地类自动强制纯 PDF
                "matched_pattern": pattern,
                "confidence": 0.95,
            }

    # ===== 第三优先级：全文总结类 =====
    for pattern in FULL_SUMMARY_PATTERNS:
        match = re.search(pattern, task_lower)
        if match:
            return {
                "intent": TaskIntent.FULL_SUMMARY,
                "explicit_pdf_only": explicit_pdf_only,
                "matched_pattern": pattern,
                "confidence": 0.9,
            }

    # ===== 第四优先级：拓展调研类（优先于精准问答，因为更明确） =====
    for pattern in EXPANSION_RESEARCH_PATTERNS:
        match = re.search(pattern, task_lower)
        if match:
            return {
                "intent": TaskIntent.EXPANSION_RESEARCH,
                "explicit_pdf_only": explicit_pdf_only,
                "matched_pattern": pattern,
                "confidence": 0.85,
            }

    # ===== 第五优先级：精准问答类 =====
    for pattern in PRECISE_QA_PATTERNS:
        match = re.search(pattern, task_lower)
        if match:
            return {
                "intent": TaskIntent.PRECISE_QA,
                "explicit_pdf_only": explicit_pdf_only,
                "matched_pattern": pattern,
                "confidence": 0.8,
            }

    # ===== 默认：通用意图 =====
    return {
        "intent": TaskIntent.GENERAL,
        "explicit_pdf_only": explicit_pdf_only,
        "matched_pattern": "",
        "confidence": 0.5,
    }


def should_force_pdf_only(intent_result: Dict[str, any]) -> bool:
    """
    判断是否应强制纯 PDF 模式（禁用联网）。

    覆盖意图：
      - DOCUMENT_LOCAL：文档本地类，强制关闭联网
      - FULL_SUMMARY：全文总结类，强制关闭联网，避免外部信息干扰
      - explicit_pdf_only：用户显式约束
    """
    intent = intent_result.get("intent")
    if intent in (TaskIntent.DOCUMENT_LOCAL, TaskIntent.FULL_SUMMARY):
        return True
    if intent_result.get("explicit_pdf_only", False):
        return True
    return False


def should_skip_sufficiency_check(intent_result: Dict[str, any]) -> bool:
    """
    判断是否应跳过所有充足度校验。
    """
    intent = intent_result.get("intent")
    return intent in (TaskIntent.DOCUMENT_LOCAL, TaskIntent.FULL_SUMMARY)


def should_skip_min_chunks_requirement(intent_result: Dict[str, any]) -> bool:
    """
    判断是否应取消最小条数硬性要求（精准问答类）。
    """
    return intent_result.get("intent") == TaskIntent.PRECISE_QA


def get_retrieval_strategy(intent_result: Dict[str, any]) -> str:
    """
    根据意图返回检索策略名称。

    返回值:
      "force_pdf_only"       — 强制纯 PDF，关闭联网
      "full_summary"         — 全文总结模式
      "precise_qa"           — 精准问答模式
      "expansion_research"   — 拓展调研模式
      "general"              — 通用模式
    """
    intent = intent_result.get("intent")

    if intent == TaskIntent.DOCUMENT_LOCAL:
        return "force_pdf_only"
    if intent == TaskIntent.FULL_SUMMARY:
        return "full_summary"
    if intent == TaskIntent.PRECISE_QA:
        return "precise_qa"
    if intent == TaskIntent.EXPANSION_RESEARCH:
        return "expansion_research"
    if intent_result.get("explicit_pdf_only", False):
        return "force_pdf_only"
    return "general"