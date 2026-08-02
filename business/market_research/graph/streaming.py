"""
【市场调研专属】流式工作流执行器

支持实时推送进度事件给前端。
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict

from core.llm.provider import get_llm
from core.utils.logger import get_logger

from business.market_research.state import AgentState
from business.market_research.nodes import (
    plan_node,
    data_ingestion_node,
    retrieval_node,
    streaming_analyst_node,
    streaming_writer_node,
    data_conflict_checker_node,
    fact_checker_node,
)
from business.market_research.graph.routing import route_after_retrieval

logger = get_logger(__name__)


async def execute_streaming_workflow(
    task: str,
    pdf_path: str = "",
    model_mode: str = "cloud",
    manual_web_search_mode: str = "auto",
    session_id: str = "",
) -> AsyncGenerator[str, None]:
    """
    执行流式工作流，实时推送进度事件。

    参数:
      task: 用户任务描述
      pdf_path: PDF 文件路径（可选）
      model_mode: 模型模式（cloud/local）
      manual_web_search_mode: 搜索模式（auto/enabled/disabled）
      session_id: 会话 ID（可选）

    生成:
      SSE 格式的事件流
    """
    # 初始化状态
    state: AgentState = {
        "task": task,
        "model_mode": model_mode,
        "manual_web_search_mode": manual_web_search_mode,
        "pdf_path": pdf_path,
        "messages": [],
        "plan": [],
        "current_step_index": 0,
        "research_results": [],
        "next_step": "",
        "web_search_used": False,
        "material_pool_frozen": False,
        "circuit_breaker_triggered": False,
        "top_k_chunks": [],
        "source_materials": [],
        "intent_override_triggered": False,
        "intent_override_target_mode": "",
        "intent_override_notification": "",
        # 规划阶段字段
        "sub_tasks": [],
        "planning_completed": False,
        # 信源溯源字段
        "citation_metadata": [],
        "conflict_alerts": [],
        "references_section": "",
        "report_with_citations": "",
        # 多源数据冲突检测字段
        "data_conflicts": [],
        "data_conflict_detected": False,
        "data_conflict_count": 0,
        "data_conflict_warnings": [],
        "data_conflict_flag": False,
        # 事实核查字段
        "fact_check_passed": False,
        "fact_check_issues": [],
        "retry_count": 0,
    }

    try:
        # ============================================================
        #  Stage 0: 规划阶段 — 前置任务拆解（市场调研独有）
        # ============================================================
        yield f"data: {json.dumps({'step': 'planning_start', 'msg': '【规划阶段】正在拆解调研需求，生成子调研方向...'})}\n\n"
        await asyncio.sleep(0.05)

        # 执行规划节点
        plan_result = plan_node(state)
        state.update(plan_result)
        sub_tasks = state.get("sub_tasks", [])

        # 推送规划完成的子任务列表到前端
        if sub_tasks:
            task_overview = []
            for i, st in enumerate(sub_tasks):
                task_overview.append({
                    "index": i + 1,
                    "sub_query": st.get("sub_query", ""),
                    "route_tag": st.get("route_tag", "pdf_web"),
                    "priority": st.get("priority", 99),
                })
            planning_event = {
                'step': 'planning_done',
                'msg': f'【规划阶段】已拆解为 {len(sub_tasks)} 个子调研方向',
                'sub_tasks': task_overview,
                'task_count': len(sub_tasks),
            }
            yield f"data: {json.dumps(planning_event, ensure_ascii=False)}\n\n"
        else:
            yield f"data: {json.dumps({'step': 'planning_done', 'msg': '规划完成，继续执行...'})}\n\n"

        await asyncio.sleep(0.1)

        if state.get("error_message"):
            yield f"data: {json.dumps({'step': 'error', 'msg': state['error_message']})}\n\n"
            return

        # ============================================================
        #  Stage 1: 数据摄入
        # ============================================================
        yield f"data: {json.dumps({'step': 'ingestion_start', 'msg': '📄 正在解析数据...'})}\n\n"
        await asyncio.sleep(0.05)
        state.update(data_ingestion_node(state))
        yield f"data: {json.dumps({'step': 'ingestion_done', 'msg': '✅ 数据解析完成'})}\n\n"

        if state.get("error_message"):
            yield f"data: {json.dumps({'step': 'error', 'msg': state['error_message']})}\n\n"
            return

        # ============================================================
        #  Stage 2: 检索
        # ============================================================
        yield f"data: {json.dumps({'step': 'retrieval_start', 'msg': '🔍 正在检索相关素材...'})}\n\n"
        await asyncio.sleep(0.05)
        state.update(retrieval_node(state))

        # 推送子任务执行进度
        sub_tasks = state.get("sub_tasks", [])
        if sub_tasks:
            current_sub = sub_tasks[0] if sub_tasks else {}
            retrieval_event = {
                'step': 'retrieval_subtask',
                'msg': f'【执行子任务】正在检索：{current_sub.get("sub_query", "")[:60]}...',
                'sub_task': current_sub.get('sub_query', ''),
                'route_tag': current_sub.get('route_tag', ''),
            }
            yield f"data: {json.dumps(retrieval_event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)

        # 推送引用元数据到前端（用于信源溯源可视化）
        citation_metadata = state.get("citation_metadata", [])
        conflict_alerts = state.get("conflict_alerts", [])
        if citation_metadata:
            citation_event = {
                'step': 'citation_metadata',
                'msg': f'📝 已生成 {len(citation_metadata)} 条引用元数据',
                'citation_count': len(citation_metadata),
                'citation_metadata': citation_metadata,
                'conflict_alerts': conflict_alerts,
            }
            yield f"data: {json.dumps(citation_event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)

        yield f"data: {json.dumps({'step': 'retrieval_done', 'msg': '✅ 检索完成'})}\n\n"

        if state.get("error_message"):
            yield f"data: {json.dumps({'step': 'error', 'msg': state['error_message']})}\n\n"
            return

        # ============================================================
        #  Stage 2.5: 轻量化多源数据冲突检测
        # ============================================================
        yield f"data: {json.dumps({'step': 'conflict_check_start', 'msg': '🔎 正在检查多源数据一致性...'})}\n\n"
        await asyncio.sleep(0.05)
        state.update(data_conflict_checker_node(state))

        data_conflicts = state.get("data_conflicts", [])
        data_conflict_detected = state.get("data_conflict_detected", False)
        if data_conflicts:
            conflict_count = state.get("data_conflict_count", 0)
            consistent_count = len([c for c in data_conflicts if c.get("status") == "consistent"])
            conflict_event = {
                'step': 'conflict_check_done',
                'msg': f'多源数据比对完成: {consistent_count} 项一致',
                'data_conflicts': data_conflicts,
                'data_conflict_detected': data_conflict_detected,
                'data_conflict_count': conflict_count,
            }
            yield f"data: {json.dumps(conflict_event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.1)
        else:
            yield f"data: {json.dumps({'step': 'conflict_check_done', 'msg': '✅ 多源数据一致，无冲突'})}\n\n"
            await asyncio.sleep(0.05)

        # ============================================================
        #  Stage 3: 分析（流式）
        # ============================================================
        async for event in streaming_analyst_node(state):
            yield event
            # 捕获 analyst_done 事件中的结果
            if event.startswith("data: ") and '"step": "analyst_done"' in event:
                try:
                    data = json.loads(event[6:])
                    state.update(data.get("result", {}))
                except Exception:
                    pass

        # ============================================================
        #  Stage 4: 写作（流式）
        # ============================================================
        async for event in streaming_writer_node(state):
            yield event
            if event.startswith("data: ") and '"step": "writer_done"' in event:
                try:
                    data = json.loads(event[6:])
                    result = data.get("result", {})
                    state["final_report"] = result.get("report", {})
                    state["citation_metadata"] = result.get("citation_metadata", [])
                    state["conflict_alerts"] = result.get("conflict_alerts", [])
                    state["references_section"] = result.get("references_section", "")
                    state["report_with_citations"] = result.get("report_with_citations", "")
                except Exception:
                    pass

        # ============================================================
        #  Stage 5: 事实核查（流式兼容）
        # ============================================================
        yield f"data: {json.dumps({'step': 'factcheck_start', 'msg': '🔎 正在执行事实核查...'})}\n\n"
        await asyncio.sleep(0.05)

        # 执行事实核查（最多重试3次）
        fact_check_passed = False
        fact_check_issues = []
        max_retries = 3
        for attempt in range(max_retries):
            check_result = fact_checker_node(state)
            state.update(check_result)
            fact_check_passed = state.get("fact_check_passed", False)
            fact_check_issues = state.get("fact_check_issues", [])

            if fact_check_passed:
                break

            if state.get("circuit_breaker_triggered"):
                break

            # 未通过，重试（重新写入）
            yield f"data: {json.dumps({'step': 'factcheck_retry', 'msg': f'⚠️ 事实核查未通过，第 {attempt + 1} 次修正...', 'retry': attempt + 1, 'max_retries': max_retries})}\n\n"
            await asyncio.sleep(0.1)

            # ===== 关键修复：如果 FactChecker 清空了 analyst_outline（整篇重写），需重新 Analyst + Writer =====
            if not state.get("analyst_outline"):
                logger.info(f"   🔄 [FactChecker] 需要整篇重写，重新 Analyst + Writer...")
                async for event in streaming_analyst_node(state):
                    yield event
                    if event.startswith("data: ") and '"step": "analyst_done"' in event:
                        try:
                            data = json.loads(event[6:])
                            state.update(data.get("result", {}))
                        except Exception:
                            pass
                async for event in streaming_writer_node(state):
                    yield event
                    if event.startswith("data: ") and '"step": "writer_done"' in event:
                        try:
                            data = json.loads(event[6:])
                            result = data.get("result", {})
                            state["final_report"] = result.get("report", {})
                            state["citation_metadata"] = result.get("citation_metadata", [])
                            state["conflict_alerts"] = result.get("conflict_alerts", [])
                            state["references_section"] = result.get("references_section", "")
                            state["report_with_citations"] = result.get("report_with_citations", "")
                        except Exception:
                            pass

        # 推送事实核查结果
        fc_event = {
            'step': 'factcheck_done',
            'msg': '✅ 事实核查通过' if fact_check_passed else f'⚠️ 事实核查完成，{len(fact_check_issues)} 个问题（已标记）',
            'fact_check_passed': fact_check_passed,
            'fact_check_issues': fact_check_issues[:10] if fact_check_issues else [],
            'circuit_breaker_triggered': state.get("circuit_breaker_triggered", False),
        }
        yield f"data: {json.dumps(fc_event, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.05)

        # ============================================================
        #  Stage 6: 完成 — 推送最终报告数据
        # ============================================================
        final_report = state.get("final_report", {})
        complete_event = {
            'step': 'done',
            'msg': '🎉 全部分析完成！',
            'session_id': session_id,
            'report': final_report,
            'fact_check_passed': fact_check_passed,
            'fact_check_issues': fact_check_issues[:10] if fact_check_issues else [],
            'circuit_breaker_triggered': state.get("circuit_breaker_triggered", False),
            'web_search_used': state.get("web_search_used", False),
        }
        yield f"data: {json.dumps(complete_event, ensure_ascii=False)}\n\n"

    except Exception as e:
        logger.error(f"流式工作流执行失败: {e}")
        yield f"data: {json.dumps({'step': 'error', 'msg': str(e)})}\n\n"