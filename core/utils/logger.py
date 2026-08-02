"""
统一日志工具 — 全局单例日志工厂（从 tools/logger 导入，保持兼容）

在 core/ 层面提供统一日志入口，实际实现委托给 tools/logger。
当 core/ 剥离为独立引擎时，可替换 tools/logger 为独立实现。
"""

import logging
from typing import Optional

# 从原有日志模块导入，保持兼容
from tools.logger import get_logger as _original_get_logger
from tools.logger import get_root_logger as _original_get_root_logger
from tools.logger import TraceIDFilter as _original_TraceIDFilter

# 重新导出，供 core/ 内部使用
def get_logger(name: str = __name__, level: Optional[int] = None) -> logging.Logger:
    """获取 Logger 实例（全局单例缓存）"""
    return _original_get_logger(name, level)


def get_root_logger() -> logging.Logger:
    """获取根日志器"""
    return _original_get_root_logger()


class TraceIDFilter(logging.Filter):
    """TraceID 过滤器"""
    def filter(self, record: logging.LogRecord) -> bool:
        return _original_TraceIDFilter().filter(record)


# 快捷实例
logger = get_logger("core.utils.logger")


__all__ = ["get_logger", "get_root_logger", "TraceIDFilter"]