"""【市场调研专属】业务状态扩展

在 core/workflow/state.py 的核心状态基础上，
增加市场调研业务特有的状态字段。
"""

from typing import Any, Dict, List, Optional
from core.workflow.state import AgentState as CoreAgentState, create_initial_state


class AgentState(CoreAgentState, total=False):
    """市场调研专属状态 — 扩展核心状态"""

    # ============================================================
    #  规划阶段（前置任务拆解 — 市场调研独有）
    # ============================================================
    sub_tasks: List[Dict[str, Any]]       # 拆解后的子任务列表
    # 每个元素: {
    #   "sub_query": str,          # 子调研问题
    #   "route_tag": str,         # 检索模式标签: pdf_only | web_only | pdf_web
    #   "judge_reason": str,      # 判定依据
    #   "priority": int,          # 执行优先级（数字越小越先执行）
    # }
    planning_completed: bool              # 规划是否已完成

    # ============================================================
    #  数据摄入
    # ============================================================
    pdf_collection: Any                  # PDF 向量集合
    cleaned_chunks: List[Dict[str, Any]]  # 清洗后的文本块

    # ============================================================
    #  分析规划
    # ============================================================
    analyst_outline: List[Dict[str, Any]]  # 分析大纲
    analyst_arguments: List[Dict[str, Any]]  # 关键论点
    report_title: str                    # 报告标题

    # ============================================================
    #  报告生成
    # ============================================================
    final_report: Any                    # 最终报告
    report_version: int                  # 报告版本号
    retry_count: int                     # 事实核查重试次数

    # ============================================================
    #  事实核查
    # ============================================================
    fact_check_passed: bool              # 事实核查是否通过
    fact_check_issues: List[Dict[str, Any]]  # 核查问题列表
    citation_validation: List[Dict[str, Any]]  # 引用验证结果

    # ============================================================
    #  搜索模式
    # ============================================================
    web_only_with_pdf_notice: str        # 纯联网模式下忽略PDF的通知

    # ============================================================
    #  规则4：防无限循环熔断
    # ============================================================
    plan_retry_count: int                # 重规划计数器（最大2次）
    plan_retry_limit_reached: bool       # 重规划是否已达上限
    timeout_triggered: bool              # 全局超时是否触发
    partial_report: Any                  # 超时截断时的部分报告
    info_limitation_note: str            # 信息局限性说明
    manual_confirm_flag: bool            # 标记【待人工确认】

    # ============================================================
    #  【新增】信源溯源与冲突识别
    # ============================================================
    citation_metadata: List[Dict[str, Any]]  # 所有引用元数据列表
    # 每个元素: {
    #   "ref_id": int,              # 引用编号 [1][2]...
    #   "source_type": str,         # "pdf" | "web"
    #   "doc_name": str,            # PDF文档名称（PDF来源）
    #   "page_num": int,            # 页码（PDF来源）
    #   "url": str,                 # 网页链接（网络来源）
    #   "snippet": str,             # 原文摘要
    #   "confidence_weight": float, # 置信权重 (0.9 / 0.6)
    #   "trust_tier": str,          # "verified" | "unverified"
    # }
    conflict_alerts: List[Dict[str, Any]]  # 冲突检测结果列表
    # 每个元素: {
    #   "topic": str,               # 冲突主题
    #   "pdf_statement": str,       # PDF 观点
    #   "web_statement": str,       # 网络观点
    #   "resolution": str,          # 处理方式：优先采信PDF
    #   "status": str,              # "conflict" | "consistent"
    # }
    report_with_citations: str             # 含角标引用的完整报告文本
    references_section: str                # 文末参考文献清单


# 重新导出 create_initial_state 供业务层使用
__all__ = ["AgentState", "create_initial_state"]