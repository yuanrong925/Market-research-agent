"""
【市场调研专属】流式工作流执行器

支持实时推送进度事件给前端。
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict

from core.utils.logger import get_logger

from business.market_research.state import AgentState
from business.market_research.session_store import get_session
from business.market_research.nodes import (
    plan_node,
    data_ingestion_node,
    retrieval_node,
    web_ingestion_node,
    streaming_analyst_node,
    streaming_writer_node,
    data_conflict_checker_node,
    chunk_validation_node,
    post_paragraph_check_node,
    paragraph_rewriter_node,
)

logger = get_logger(__name__)


async def execute_streaming_workflow(
    task: str,
    pdf_path: str = "",
    model_mode: str = "cloud",
    manual_web_search_mode: str = "auto",
    model_name: str = "",
    session_id: str = "",
) -> AsyncGenerator[str, None]:
    """
    执行流式工作流，实时推送进度事件。

    参数:
      task: 用户任务描述
      pdf_path: PDF 文件路径（可选）
      model_mode: 模型模式（cloud/local）
      manual_web_search_mode: 搜索模式（auto/enabled/disabled）
      model_name: 具体模型名称（local 模式下生效，如 qwen2.5:7b）
      session_id: 会话 ID（可选）

    生成:
      SSE 格式的事件流
    """
    # 初始化状态
    state: Dict[str, Any] = {
        "task": task,
        "model_mode": model_mode,
        "model_name": model_name,
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
        # 早停字段
        "early_terminate": False,
        "info_limitation_note": "",
        # Chunk 校验字段
        "validation_stats": {},
        "web_cleaned_chunks": [],
        "chunks_validated": False,
        # Web 入库字段
        "unified_collection": None,
        "web_chunks_validated": False,
        "web_chunks_in_db": 0,
        # 后置校验字段
        "post_check_results": [],
        "post_check_rewrite_count": 0,
        "post_check_passed": True,
        "post_check_meltdown": False,
        "rewrite_scope": [],
    }

    # ===== SSE 心跳：每 30s 发送一次 keep-alive 防止连接超时 =====
    _heartbeat_ts = [time.time()]  # 使用列表模拟可变闭包

    def _should_heartbeat() -> bool:
        now = time.time()
        if now - _heartbeat_ts[0] >= 30:
            _heartbeat_ts[0] = now
            return True
        return False

    try:
        # ===== 首次心跳检查 =====
        if _should_heartbeat():
            yield f"data: {json.dumps({'step': 'heartbeat', 'ts': time.time()})}\n\n"

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
            yield f"data: {json.dumps(planning_event, ensure_ascii=False, default=str)}\n\n"
        else:
            yield f"data: {json.dumps({'step': 'planning_done', 'msg': '规划完成，继续执行...'})}\n\n"

        await asyncio.sleep(0.1)

        # ===== Mode notification for user awareness =====
        # 根据用户选择的模式，向前端发送明确的模式提示，让用户知道当前生效的搜索模式
        has_pdf = bool(state.get("pdf_path", ""))
        manual_mode = state.get("manual_web_search_mode", "auto").lower()

        # 场景1: PDF+联网模式 + 未上传PDF → 自动降级为纯联网
        if manual_mode in ("auto", "pdf_web") and not has_pdf:
            mode_notification = (
                "📢 您选择了【PDF+联网】模式但未上传PDF文档，系统已自动降级为【纯联网】模式，"
                "仅基于公开网络信息进行分析。如需上传文档，请重新发起请求时附上PDF文件。"
            )
            mode_event = {
                'step': 'mode_notification',
                'notification': mode_notification,
                'mode': 'degraded_to_web_only',
                'mode_label': '🔍 纯联网（自动降级）',
                'mode_color': '#f59e0b',
            }
            yield f"data: {json.dumps(mode_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.05)

        # 场景2: 纯联网模式 + 上传了PDF → 告知用户已忽略PDF
        elif manual_mode in ("enabled", "web_only") and has_pdf:
            mode_notification = (
                "📢 您选择了【纯联网】模式，系统已忽略上传的PDF文档，仅使用公开网络信息进行分析。"
                "如需使用PDF内容，请切换至【PDF+联网】或【仅PDF】模式。"
            )
            mode_event = {
                'step': 'mode_notification',
                'notification': mode_notification,
                'mode': 'web_only_ignored_pdf',
                'mode_label': '🔍 纯联网（已忽略PDF）',
                'mode_color': '#f59e0b',
            }
            yield f"data: {json.dumps(mode_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.05)

        # 场景3: 仅PDF模式 + 有PDF → 告诉用户正在使用仅PDF模式
        elif manual_mode in ("disabled", "pdf_only") and has_pdf:
            mode_notification = (
                "📄 当前为【仅PDF】模式，仅基于上传的PDF文档进行分析，不会联网搜索。"
            )
            mode_event = {
                'step': 'mode_notification',
                'notification': mode_notification,
                'mode': 'pdf_only',
                'mode_label': '📄 仅PDF',
                'mode_color': '#2563eb',
            }
            yield f"data: {json.dumps(mode_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.05)

        # 场景4: 仅PDF模式 + 未上传PDF → 后端已拦截，但需要通知前端更新模式指示器
        if manual_mode in ("disabled", "pdf_only") and not has_pdf:
            mode_notification = (
                "📄 您选择了【仅PDF】模式，但未上传PDF文档。此模式必须上传PDF文件才能运行，"
                "请上传PDF文档或切换至其他模式。"
            )
            mode_event = {
                'step': 'mode_notification',
                'notification': mode_notification,
                'mode': 'pdf_only_no_pdf',
                'mode_label': '❌ 仅PDF（缺少PDF文件）',
                'mode_color': '#ef4444',
            }
            yield f"data: {json.dumps(mode_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.05)

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
                'step': 'subtask_retrieval',
                'msg': f'【执行子任务】正在检索：{current_sub.get("sub_query", "")[:60]}...',
                'sub_task': current_sub.get('sub_query', ''),
                'route_tag': current_sub.get('route_tag', ''),
            }
            yield f"data: {json.dumps(retrieval_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.1)

        # 早停检查：检索发现全部子任务不相关/文档无数据 → 直接截停
        if state.get("early_terminate"):
            term_msg = state.get("error_message", "检索未发现有效信息，已自动停止分析")
            info_note = state.get("info_limitation_note", "")
            yield f"data: {json.dumps({'step': 'early_terminate', 'msg': term_msg, 'info_limitation_note': info_note})}\n\n"
            await asyncio.sleep(0.05)
            # 推送完成事件带空报告
            yield f"data: {json.dumps({'step': 'early_terminate', 'msg': '⏹️ 分析已提前终止', 'session_id': session_id, 'report': {}, 'early_terminate': True, 'info_limitation_note': info_note})}\n\n"
            return

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
            yield f"data: {json.dumps(citation_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.05)

        # 检查是否 web_only 模式忽略了PDF，推送通知
        retrieval_notification = ""
        if state.get("manual_web_search_mode", "auto").lower() in ("enabled", "web_only") and state.get("pdf_path"):
            retrieval_notification = "🔍 纯联网模式已忽略上传的PDF，仅使用网络搜索结果"

        yield f"data: {json.dumps({'step': 'retrieval_done', 'msg': '✅ 检索完成', 'notification': retrieval_notification})}\n\n"

        if state.get("error_message"):
            yield f"data: {json.dumps({'step': 'error', 'msg': state['error_message']})}\n\n"
            return

        # ============================================================
        #  Stage 2.25: Web 网页切片入库
        # ============================================================
        yield f"data: {json.dumps({'step': 'web_ingestion_start', 'msg': '🌐 正在清洗网页切片并入库...'})}\n\n"
        await asyncio.sleep(0.05)
        state.update(web_ingestion_node(state))

        web_chunks_in_db = state.get("web_chunks_in_db", 0)
        yield f"data: {json.dumps({'step': 'web_ingestion_done', 'msg': '✅ Web 切片入库完成: %d 条' % web_chunks_in_db})}\n\n"
        await asyncio.sleep(0.05)

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
            yield f"data: {json.dumps(conflict_event, ensure_ascii=False, default=str)}\n\n"
            await asyncio.sleep(0.1)
        else:
            yield f"data: {json.dumps({'step': 'conflict_check_done', 'msg': '✅ 多源数据一致，无冲突'})}\n\n"
            await asyncio.sleep(0.05)

        # ============================================================
        #  Stage 2.75: Chunk 统一校验
        # ============================================================
        yield f"data: {json.dumps({'step': 'validation_start', 'msg': '✅ 正在校验素材一致性...'})}\n\n"
        await asyncio.sleep(0.05)
        state.update(chunk_validation_node(state))

        validation_stats = state.get("validation_stats", {})
        passed_count = validation_stats.get("passed", 0)
        rejected_count = validation_stats.get("rejected", 0)
        validation_event = {
            "step": "validation_done",
            "msg": f"素材校验完成: {passed_count} 条通过, {rejected_count} 条剔除",
            "validation_stats": validation_stats,
        }
        yield f"data: {json.dumps(validation_event, ensure_ascii=False, default=str)}\n\n"
        await asyncio.sleep(0.05)

        # ============================================================
        #  Stage 2.8: 二次检索（素材不足时自动补充）
        # ============================================================
        validation_summary = state.get("validation_summary", {})
        needs_retrieval = validation_summary.get("needs_retrieval", False)
        missing_sub_tasks = validation_summary.get("missing_sub_tasks", [])
        MAX_RETRIEVAL_RETRIES = 2
        retrieval_retry_count = 0

        while needs_retrieval and retrieval_retry_count < MAX_RETRIEVAL_RETRIES:
            retrieval_retry_count += 1
            missing_text = "、".join(missing_sub_tasks[:3])
            logger.info(f"   [二次检索] 第 {retrieval_retry_count} 次: 素材不足 ({validation_summary.get('passed_count', 0)}/2)，缺少方向: {missing_text}")
            yield f"data: {json.dumps({'step': 'supplement_retrieval_start', 'msg': f'🔍 素材不足，正在补充检索（第 {retrieval_retry_count} 次）...', 'missing_sub_tasks': missing_sub_tasks})}\n\n"
            await asyncio.sleep(0.05)

            # 执行二次检索
            state.update(retrieval_node(state))
            yield f"data: {json.dumps({'step': 'supplement_retrieval_done', 'msg': '✅ 补充检索完成，重新校验...'})}\n\n"
            await asyncio.sleep(0.05)

            # 重新校验
            state.update(web_ingestion_node(state))
            state.update(chunk_validation_node(state))

            validation_summary = state.get("validation_summary", {})
            needs_retrieval = validation_summary.get("needs_retrieval", False)
            missing_sub_tasks = validation_summary.get("missing_sub_tasks", [])

            passed_count = validation_summary.get("passed_count", 0)
            yield f"data: {json.dumps({'step': 'supplement_retrieval_result', 'msg': f'二次检索后素材: {passed_count} 条通过', 'passed_count': passed_count, 'needs_retrieval': needs_retrieval})}\n\n"
            await asyncio.sleep(0.05)

        if needs_retrieval and retrieval_retry_count >= MAX_RETRIEVAL_RETRIES:
            logger.info(f"   [二次检索] 达到最大重试次数 ({MAX_RETRIEVAL_RETRIES})，使用现有素材继续")
            maxed_msg = f'⚠️ 已达到最大补充检索次数，使用现有 {validation_summary.get("passed_count", 0)} 条素材继续'
            yield f"data: {json.dumps({'step': 'supplement_retrieval_maxed', 'msg': maxed_msg})}\n\n"
            await asyncio.sleep(0.05)

        # ============================================================
        #  Stage 3: 分析（流式）
        # ============================================================
        async for event in streaming_analyst_node(state):
            yield event
            # 捕获 analyst_done 事件中的结果
            if event.startswith("data: ") and '"step": "analyst_done"' in event:
                try:
                    data = json.loads(event[6:].strip())
                    state.update(data.get("result", {}))
                except Exception as e:
                    logger.warning(f"   [Streaming] 解析分析完成事件失败: {e}, event={event[:80]}")

        # ============================================================
        #  Stage 4: 写作（流式）
        # ============================================================
        async for event in streaming_writer_node(state):
            yield event
            if event.startswith("data: ") and '"step": "writer_done"' in event:
                try:
                    data = json.loads(event[6:].strip())
                    result = data.get("result", {})
                    state["final_report"] = result.get("report", {})
                    state["citation_metadata"] = result.get("citation_metadata", [])
                    state["conflict_alerts"] = result.get("conflict_alerts", [])
                    state["references_section"] = result.get("references_section", "")
                    state["report_with_citations"] = result.get("report_with_citations", "")
                except Exception as e:
                    logger.warning(f"   [Streaming] 解析写作完成事件失败: {e}, event={event[:80]}")
                    # 解析失败时置空报告，让下游 post_paragraph_check_node 的判空逻辑生效
                    state["final_report"] = {}
                    state["report_with_citations"] = "{}"

        # ============================================================
        #  Stage 4.5: 后置段落校验（写作后、事实核查前）
        # ============================================================
        yield f"data: {json.dumps({'step': 'post_check_start', 'msg': '🔎 正在执行后置段落校验...'})}\n\n"
        await asyncio.sleep(0.05)

        # 执行后置段落校验
        post_check_result = post_paragraph_check_node(state)
        state.update(post_check_result)

        post_check_passed = state.get("post_check_passed", True)
        post_check_meltdown = state.get("post_check_meltdown", False)
        rewrite_count = state.get("post_check_rewrite_count", 0)

        # 推送后置校验结果
        yield f"data: {json.dumps({'step': 'post_check_done', 'msg': ('✅ 后置校验通过' if post_check_passed else '⚠️ 后置校验发现需要重写 (第 %d 次)' % rewrite_count), 'post_check_passed': post_check_passed, 'post_check_meltdown': post_check_meltdown, 'rewrite_scope': state.get('rewrite_scope', [])})}\n\n"
        await asyncio.sleep(0.05)

        # 如果发现数字问题，按比例决策：
        #   > 30% → 自动修正（只改数字，最多1次）
        #   ≤ 30% → 直接输出，返回用户人工选择
        issue_ratio = state.get('post_check_issue_ratio', 0)
        issue_count = state.get('post_check_issue_count', 0)
        total_numbers = state.get('post_check_total_numbers', 0)

        if not post_check_passed and not post_check_meltdown:
            if issue_ratio > 30:
                # 问题比例 > 30% → 执行1次数字修正
                yield f"data: {json.dumps({'step': 'number_rewrite_start', 'msg': '✏️ 问题比例 %.1f%% > 30%，正在执行数字修正...' % issue_ratio})}\n\n"
                await asyncio.sleep(0.05)

                rewrite_result = paragraph_rewriter_node(state)
                state.update(rewrite_result)

                yield f"data: {json.dumps({'step': 'number_rewrite_done', 'msg': '✅ 数字修正完成'})}\n\n"
                await asyncio.sleep(0.05)

                # 修正后直接结束
                post_check_passed = True
            else:
                # 问题比例 ≤ 30% → 直接输出，返回用户人工选择
                yield f"data: {json.dumps({'step': 'manual_confirm', 'msg': '📋 问题比例 %.1f%% (%d/%d) ≤ 30%，已原样输出，需人工确认' % (issue_ratio, issue_count, total_numbers)})}\n\n"
                await asyncio.sleep(0.05)

                state["manual_confirm_flag"] = True
                state["info_limitation_note"] = (
                    f"后置数字校验发现 {issue_count}/{total_numbers} 个数字存在问题（占比 {issue_ratio}%），"
                    f"低于自动修正阈值（30%），已原样输出，请人工逐项确认。"
                )

        # ============================================================
        #  Stage 5: 完成 — 推送最终报告数据
        # ============================================================
        final_report = state.get("final_report", {})

        # 将「信息来源附录」放到报告最后（前端 priorityKeys 最后一项）
        ref_section = state.get("references_section", "")
        if ref_section:
            if isinstance(final_report, dict):
                # 解析附录为结构化引用列表
                sources_list = []
                for line in ref_section.split("\n"):
                    stripped = line.strip()
                    # 匹配 【S1】... 格式，保留完整引用描述
                    if stripped.startswith("【S") and "】" in stripped:
                        # 去除外层引号（如果有）
                        clean = stripped.strip('"')
                        if clean:
                            sources_list.append(clean)
                if sources_list:
                    final_report["信息来源附录"] = sources_list

        # 将最终报告写入 session，供后续追问接口和 api.py 使用
        try:
            session = get_session(session_id)
            if session:
                session["final_report"] = final_report
                session["web_search_used"] = state.get("web_search_used", False)
        except Exception as e:
            logger.warning(f"   [Streaming] 写入 session 失败: {e}")

        complete_event = {
            'step': 'done',
            'msg': '🎉 全部分析完成！',
            'session_id': session_id,
            'report': final_report,
            'web_search_used': state.get("web_search_used", False),
        }
        yield f"data: {json.dumps(complete_event, ensure_ascii=False, default=str)}\n\n"

    except Exception as e:
        logger.error(f"流式工作流执行失败: {e}")
        yield f"data: {json.dumps({'step': 'error', 'msg': str(e)})}\n\n"
