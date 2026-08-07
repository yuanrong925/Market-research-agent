"""
【已删除】事实核查节点（FactChecker）— 已根据用户要求移除。

fact_checker_node 已完全删除，不再执行任何事实核查。
后置校验由 post_paragraph_check_node 全权负责。
"""

from core.utils.logger import get_logger

logger = get_logger(__name__)


def fact_checker_node(state):
    """
    【已删除】事实核查节点 — 已移除，不再调用。
    保留此函数仅作为占位符，避免导入报错，返回直通结果。
    """
    logger.info("   [FactChecker] 已移除，跳过")
    return {
        "fact_check_passed": True,
        "fact_check_issues": [],
        "retry_count": 0,
    }
