"""Core Engine 配置模块 — 读取环境变量，提供全局配置"""

import os
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class AppConfig:
    """全局应用配置 — 纯净版，不含任何业务逻辑"""

    # ============================================================
    #  模型配置
    # ============================================================
    model_mode: str = field(default_factory=lambda: os.getenv("MODEL_MODE", "cloud").strip().lower() or "cloud")

    # 本地 Ollama
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen:7b"))
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"))

    # DeepSeek
    cloud_api_key: str = field(default_factory=lambda: os.getenv("CLOUD_API_KEY", ""))
    cloud_base_url: str = field(default_factory=lambda: os.getenv("CLOUD_BASE_URL", "https://api.deepseek.com"))
    cloud_model: str = field(default_factory=lambda: os.getenv("CLOUD_MODEL", "deepseek-v4-flash"))

    # 通义千问
    dashscope_api_key: str = field(default_factory=lambda: os.getenv("DASHSCOPE_API_KEY", ""))
    qwen_api_key: str = field(default_factory=lambda: os.getenv("QWEN_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", ""))
    qwen_base_url: str = field(default_factory=lambda: os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
    qwen_model: str = field(default_factory=lambda: os.getenv("QWEN_MODEL", "qwen-turbo"))

    # Embedding
    embedding_provider: str = field(default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "dashscope").strip().lower())
    embedding_model: str = "text-embedding-v3"
    embedding_base_url: str = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"

    # ============================================================
    #  搜索引擎配置
    # ============================================================
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    web_search_enabled: bool = field(
        default_factory=lambda: os.getenv("WEB_SEARCH_ENABLED", "true").strip().lower() in ("true", "1", "yes")
    )
    max_search_rounds: int = 2

    trusted_domains: List[str] = field(default_factory=lambda: [
        ".gov", ".gov.cn", ".stats.gov", ".mofcom.gov",
        ".who.int", ".un.org", ".worldbank.org", ".imf.org",
        ".gartner.com", ".idc.com", ".mckinsey.com", ".bain.com",
        ".deloitte.com", ".pwc.com", ".accenture.com",
        ".bloomberg.com", ".reuters.com",
        ".wsj.com", ".ft.com", ".economist.com",
        ".edu", ".edu.cn", ".ac.cn", ".arxiv.org",
        ".gs.com", ".jpmorgan.com", ".ms.com",
    ])

    low_quality_domains: List[str] = field(default_factory=lambda: [
        "csdn.net", "jianshu.com", "douban.com",
        "baidu.com/home", "sohu.com/a/", "163.com/dy/",
        "zhuanlan.zhihu.com",
        "xiaohongshu.com",
        "toutiao.com", "tiktok.com",
    ])

    # ============================================================
    #  项目路径
    # ============================================================
    project_root: str = field(default_factory=lambda: os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    chroma_db_dir: str = field(default_factory=lambda: os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db"
    ))

    # ============================================================
    #  计算属性
    # ============================================================
    @property
    def is_local_mode(self) -> bool:
        return self.model_mode == "local"

    @property
    def is_cloud_mode(self) -> bool:
        return self.model_mode == "cloud"

    def __post_init__(self):
        # 确保 tavily api key 传递到环境变量
        if self.tavily_api_key:
            os.environ["TAVILY_API_KEY"] = self.tavily_api_key


# 全局单例
_config_instance: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局配置单例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = AppConfig()
    return _config_instance


# 兼容旧接口
def get_env(key: str, default: str = "") -> str:
    return os.getenv(key, default)