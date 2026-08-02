"""节点模块 — 工作流中每个独立节点

每个节点是一个独立的 Python 文件，遵循 SOP 五阶段规范。
"""

from business.market_research.nodes.ingestion import data_ingestion_node
from nodes.retrieval import retrieval_node
from nodes.analyst import analyst_node, streaming_analyst_node
from nodes.writer import writer_node, streaming_writer_node
from nodes.checker import fact_checker_node

__all__ = [
    "data_ingestion_node",
    "retrieval_node",
    "analyst_node",
    "streaming_analyst_node",
    "writer_node",
    "streaming_writer_node",
    "fact_checker_node",
]