"""工作流模块 — 图定义、路由、流转逻辑"""

from workflow.graph import build_workflow, build_legacy_workflow
from workflow.routing import (
    route_after_ingestion,
    route_after_retrieval,
    route_after_analyst,
    route_after_writer,
    route_after_fact_check,
    route_after_plan,
    route_after_research,
    route_after_writer_deprecated,
    route_after_fact_check_deprecated,
)
from workflow.streaming import (
    run_streaming_workflow,
    run_followup_streaming_workflow,
)

__all__ = [
    "build_workflow",
    "build_legacy_workflow",
    "route_after_ingestion",
    "route_after_retrieval",
    "route_after_analyst",
    "route_after_writer",
    "route_after_fact_check",
    "route_after_plan",
    "route_after_research",
    "route_after_writer_deprecated",
    "route_after_fact_check_deprecated",
    "run_streaming_workflow",
    "run_followup_streaming_workflow",
]