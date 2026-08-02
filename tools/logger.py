"""
统一日志工具 — 全局单例日志工厂

职责：
  1. 统一日志格式、日志分级、文件轮转、控制台双输出、自动识别模块名
  2. 区分 DEBUG/INFO/WARNING/ERROR/CRITICAL 五级日志
  3. 日志同时输出控制台 + 本地 logs/ 文件夹（按日期分割日志文件）
  4. 自动打印：时间 | 日志等级 | 模块文件 | 函数名 | 行号
  5. 支持环境变量 LOG_LEVEL 控制日志等级（本地 DEBUG，线上 INFO/ERROR）

用法：
  from tools.logger import get_logger
  logger = get_logger(__name__)
  logger.info("这是信息")
  logger.debug("这是调试")
  logger.error("这是错误", exc_info=True)
"""
import glob
import logging
import os
import re
import sys
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
from typing import Optional


# ============================================================
#  TraceID 过滤器
# ============================================================

class TraceIDFilter(logging.Filter):
    """
    自动将 trace_id 注入日志记录。
    ContextVar 用于跨异步/线程传递 trace_id。
    """
    _trace_id_var = None

    @classmethod
    def _get_var(cls):
        if cls._trace_id_var is None:
            try:
                from contextvars import ContextVar
                cls._trace_id_var = ContextVar('trace_id', default='')
            except Exception:
                cls._trace_id_var = None
        return cls._trace_id_var

    @classmethod
    def set_trace_id(cls, trace_id: str):
        var = cls._get_var()
        if var is not None:
            var.set(trace_id)

    @classmethod
    def get_trace_id(cls) -> str:
        var = cls._get_var()
        if var is not None:
            return var.get()
        return ''

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = self.get_trace_id()
        if trace_id:
            record.trace_id = trace_id
        else:
            record.trace_id = getattr(record, 'trace_id', '-')
        return True


# ============================================================
#  敏感信息脱敏过滤器
# ============================================================

_SENSITIVE_PATTERNS = [
    (re.compile(r'(sk-)[a-zA-Z0-9]{20,}', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r'(tvly-)[a-zA-Z0-9]{20,}', re.IGNORECASE), r'\1***REDACTED***'),
    (re.compile(r"""(api[_\-]?key\s*[=:']\s*['"]?)[a-zA-Z0-9_\-]{8,}""", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"""(secret[_\-]?key\s*[=:']\s*['"]?)[a-zA-Z0-9_\-]{8,}""", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"""(password\s*[=:']\s*['"]?)[a-zA-Z0-9]{4,}""", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"""(token\s*[=:']\s*['"]?)[a-zA-Z0-9_\-]{8,}""", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r'(Authorization:?\s*)(Bearer\s+)?[a-zA-Z0-9_\-]{8,}', re.IGNORECASE), r'\1***REDACTED***'),
]


class SensitiveDataFilter(logging.Filter):
    """自动过滤日志中的敏感信息（API Key、密钥等）"""

    def filter(self, record: logging.LogRecord) -> bool:
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            for pattern, replacement in _SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        if hasattr(record, 'args') and record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in _SENSITIVE_PATTERNS:
                        arg = pattern.sub(replacement, arg)
                new_args.append(arg)
            record.args = tuple(new_args)
        return True


# ============================================================
#  日志文件清理
# ============================================================

def _cleanup_old_logs(log_dir: str, retention_days: int):
    """清理超过 retention_days 的旧日志文件"""
    import time as _time
    now = _time.time()
    cutoff = now - retention_days * 86400
    for fpath in glob.glob(os.path.join(log_dir, 'market-research-agent.log.*')):
        try:
            if os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
        except OSError:
            pass



# ============================================================
#  全局配置
# ============================================================

# 日志等级映射
_LOG_LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}

# 默认日志等级（可通过环境变量 LOG_LEVEL 覆盖）
_DEFAULT_LOG_LEVEL = os.getenv("LOG_LEVEL", "debug").strip().lower()
_LOG_LEVEL = _LOG_LEVEL_MAP.get(_DEFAULT_LOG_LEVEL, logging.DEBUG)

# 日志文件目录
_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

# 日志格式
_LOG_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(trace_id)-12s | %(name)s | %(funcName)s:%(lineno)d | %(message)s"
)
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 控制台日志格式（更简洁，无模块名）
_CONSOLE_FORMAT = (
    "%(asctime)s | %(levelname)-5s | %(trace_id)-12s | %(funcName)s:%(lineno)d | %(message)s"
)

# 单例缓存：_logger_cache[name] = logger
_logger_cache: dict = {}


# ============================================================
#  日志工厂
# ============================================================


def _parse_max_size(size_str: str) -> int:
    """将容量字符串（如 '10MB', '100MB', '1GB'）转换为字节数"""
    size_str = size_str.strip().upper()
    match = re.match(r'^(\d+(\.\d+)?)\s*(KB|MB|GB|TB)?$', size_str)
    if not match:
        return 10 * 1024 * 1024  # 默认 10MB
    num = float(match.group(1))
    unit = match.group(3) or 'MB'
    multipliers = {'KB': 1024, 'MB': 1024 * 1024, 'GB': 1024 * 1024 * 1024, 'TB': 1024 * 1024 * 1024 * 1024}
    return int(num * multipliers.get(unit, 1024 * 1024))



def get_logger(name: str = __name__, level: Optional[int] = None) -> logging.Logger:
    """
    获取 Logger 实例（全局单例缓存）。

    参数：
      name: 模块名，通常传入 __name__
      level: 可选的日志等级覆盖，不传则使用全局 _LOG_LEVEL

    返回：
      logging.Logger 实例
    """
    # 缓存命中直接返回
    if name in _logger_cache:
        return _logger_cache[name]

    logger = logging.getLogger(name)
    effective_level = level if level is not None else _LOG_LEVEL
    logger.setLevel(effective_level)

    # 防止重复添加 handler
    if logger.handlers:
        _logger_cache[name] = logger
        return logger

    # ---- 创建日志目录 ----
    os.makedirs(_LOG_DIR, exist_ok=True)

    # ---- 判断是否保存日志文件 ----
    log_save_file = os.getenv("LOG_SAVE_FILE", "true").strip().lower() in ("true", "1", "yes")

    if log_save_file:
        # ---- 1. 文件 Handler（按日期分割 + 按大小轮转） ----
        log_file = os.path.join(_LOG_DIR, "market-research-agent.log")
        log_max_size_str = os.getenv("LOG_MAX_SIZE", "10MB")
        log_max_size = _parse_max_size(log_max_size_str)
        log_retention_days = int(os.getenv("LOG_RETENTION_DAYS", "7"))

        file_handler = TimedRotatingFileHandler(
            filename=log_file,
            when="midnight",           # 每天零点轮转
            interval=1,
            backupCount=log_retention_days,  # 保留天数
            encoding="utf-8",
            delay=False,
        )
        file_handler.setLevel(logging.DEBUG)  # 文件记录所有级别
        file_formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
        file_handler.setFormatter(file_formatter)

    # ---- 2. 控制台 Handler ----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(effective_level)
    console_formatter = logging.Formatter(_CONSOLE_FORMAT, datefmt=_DATE_FORMAT)
    console_handler.setFormatter(console_formatter)

    # ---- 添加 TraceID 和敏感信息过滤器 ----
    trace_filter = TraceIDFilter()
    sensitive_filter = SensitiveDataFilter()
    logger.addFilter(trace_filter)
    logger.addFilter(sensitive_filter)

    # ---- 添加 Handler ----
    if log_save_file:
        logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # ---- 自动清理旧日志 ----
    try:
        _cleanup_old_logs(_LOG_DIR, int(os.getenv("LOG_RETENTION_DAYS", "7")))
    except Exception:
        pass

    # 缓存
    _logger_cache[name] = logger

    return logger


# ============================================================
#  便捷函数：快速获取根日志器
# ============================================================

def get_root_logger() -> logging.Logger:
    """获取根日志器（用于启动时一次性配置）"""
    return get_logger("market-research-agent")


# ============================================================
#  模块级快捷实例
# ============================================================

# 当直接 from tools.logger import logger 时使用
logger = get_logger("tools.logger")
