"""
# Core Engine — 底层检索调度引擎

## 设计原则
1. **垂直领域无关** — core/ 不包含任何市场调研特定逻辑，可被任意垂直化场景复用
2. **分层解耦** — 每一层（LLM、Embedding、检索、搜索引擎、工作流）都有抽象接口，
   实现可独立替换
3. **可剥离** — 移除 core/ 目录不会影响 market_research 业务逻辑的独立性

## 目录结构
```
core/
├── __init__.py          # 模块入口
├── config.py            # 基础配置（环境变量解析）
├── branding.py          # 垂直化烙印
├── llm/                 # LLM 抽象层
│   ├── __init__.py
│   └── provider.py      # 统一 LLM 接口（deepseek / qwen / ollama）
├── embedding/           # Embedding 抽象层
│   ├── __init__.py
│   └── provider.py      # 统一 Embedding 接口（dashscope / openai / local_bge）
├── retrieval/           # 检索调度引擎
│   ├── __init__.py
│   ├── chroma.py        # ChromaDB 客户端
│   ├── hybrid.py        # 混合检索（向量+BM25）+ RRF 融合评分
│   └── reranker.py      # 重排序（保留接口，可扩展）
├── search/              # 搜索引擎
│   ├── __init__.py
│   └── provider.py      # 统一搜索接口（tavily / duckduckgo）
├── workflow/            # 工作流引擎
│   ├── __init__.py
│   ├── state.py         # 基础状态定义
│   ├── graph.py         # 工作流图构建器
│   ├── routing.py       # 路由逻辑
│   └── streaming.py     # 流式输出支持
└── utils/               # 核心工具
    ├── __init__.py
    └── logger.py        # 结构化日志
```
"""

# 版本信息
__version__ = "1.0.0"
__description__ = "Core Engine — 底层检索调度引擎（垂直领域无关）"

from core.config import AppConfig
from core.branding import get_branding_info

__all__ = ["AppConfig", "get_branding_info"]