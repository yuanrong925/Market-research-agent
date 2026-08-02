"""流式工作流 — SSE 实时推送全流程进度"""

import asyncio
import json
import os
import tempfile
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional
from tools.logger import get_logger

logger = get_logger(__name__)

# ============================================================
#  流式推理超时配置（秒）
# ============================================================
_STREAM_TIMEOUT = 120  # 120 秒后强制退出循环，防止节点悬停


from langchain_core.messages import HumanMessage, SystemMessage

from agents.config import get_llm_streaming
from business.market_research.nodes.ingestion import data_ingestion_node
from nodes.retrieval import retrieval_node
from nodes.analyst import streaming_analyst_node
from nodes.writer import streaming_writer_node
from agents.retrieval.rag import generate_pdf_report
from tools.llm_utils import extract_text_content, is_stream_finished

# 会话管理器（多轮对话）
try:
    from agents.session_store import create_session, get_session, append_conversation, get_conversation_history
except ImportError:
    create_session = get_session = append_conversation = get_conversation_history = None


async def run_streaming_workflow(
    task: str,
    pdf_collection: Optional[object] = None,
    model_mode: str = "cloud",
    manual_web_search_mode: str = "auto",
    intent_override_triggered: bool = False,
    intent_override_target_mode: str = "",
    intent_override_notification: str = "",
) -> AsyncGenerator[str, None]:
    """
    完整的流式工作流：PDF解析 → 检索 → Analyst(流式) → Writer(流式) → PDF生成。
    每个阶段通过 SSE yield 事件到前端。
    """
    # ---- Step 0: 初始化 state ----
    state: Dict[str, Any] = {
        "task": task,
        "messages": [],
        "plan": [],
        "current_step_index": 0,
        "research_results": [],
        "final_report": "",
        "next_step": "",
        "pdf_collection": pdf_collection,
        "model_mode": model_mode,
        "manual_web_search_mode": manual_web_search_mode,
        "fact_check_passed": True,
        "fact_check_issues": [],
        "source_materials": [],
        "citation_validation": [],
        "cleaned_chunks": [],
        "top_k_chunks": [],
        "analyst_outline": [],
        "analyst_arguments": [],
        "report_version": 0,
        "retry_count": 0,
        "circuit_breaker_triggered": False,
        "error_log_package": None,
        "web_search_used": False,
        "material_pool_frozen": False,
        "intent_override_triggered": intent_override_triggered,
        "intent_override_target_mode": intent_override_target_mode,
        "intent_override_notification": intent_override_notification,
    }

    logger.info(f"🚀 [Workflow] 流式工作流启动: task={task[:40]}..., model={model_mode}")
    _workflow_start = __import__("time").time()
    # ---- Step 0.5: 意图识别兜底通知（如果触发了模式覆盖） ----
    if intent_override_triggered and intent_override_notification:
        logger.info(f"   🔔 [意图兜底] {intent_override_notification}")
        yield f"data: {json.dumps({'step': 'intent_override', 'msg': intent_override_notification, 'notification': intent_override_notification, 'overridden_mode': intent_override_target_mode})}\n\n"
        await asyncio.sleep(0.05)

    # ---- Step 1: 数据摄入 ----
    yield f"data: {json.dumps({'step': 'ingestion_start', 'msg': '正在解析数据...'})}\n\n"
    await asyncio.sleep(0.05)

    try:
        result = data_ingestion_node(state)
        state.update(result)
        chunk_count = len(state.get("cleaned_chunks", []))
        yield f"data: {json.dumps({'step': 'ingestion_done', 'msg': f'数据解析完成: {chunk_count} 个文本块'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'数据摄入失败: {str(e)}'})}\n\n"
        return

    # ---- Step 2: 检索 ----
    yield f"data: {json.dumps({'step': 'retrieval_start', 'msg': '正在检索相关素材...'})}\n\n"
    await asyncio.sleep(0.05)

    try:
        result = retrieval_node(state)
        state.update(result)
        state["top_k_chunks"] = [
            c if isinstance(c, dict) else {"text": str(c), "source_index": i}
            for i, c in enumerate(state.get("top_k_chunks", []))
        ]
        retrieval_count = len(state.get("top_k_chunks", []))
        # 检查是否有 web_only 模式下的PDF忽略通知
        web_only_notice = state.get("web_only_with_pdf_notice", "")
        if web_only_notice:
            yield f"data: {json.dumps({'step': 'retrieval_done', 'msg': web_only_notice, 'notification': web_only_notice})}\n\n"
        else:
            yield f"data: {json.dumps({'step': 'retrieval_done', 'msg': f'检索完成: {retrieval_count} 个高置信度片段'})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'检索失败: {str(e)}'})}\n\n"
        return

    # ---- Step 3: Analyst 流式生成大纲 ----
    state["report_title"] = task
    analyst_result = None
    async for event in streaming_analyst_node(state):
        yield event
        if '"step": "analyst_done"' in event:
            try:
                payload = json.loads(event[6:])
                analyst_result = payload.get("result", {})
            except Exception:
                pass

    if analyst_result:
        state["analyst_outline"] = analyst_result.get("analyst_outline", [])
        state["analyst_arguments"] = analyst_result.get("analyst_arguments", [])
        state["report_title"] = analyst_result.get("report_title", task)
        logger.info(f"   📋 流式 Analyst 完成: {len(state['analyst_outline'])} 章节, {len(state['analyst_arguments'])} 论点")

    # ---- Step 4: Writer 流式生成报告 ----
    final_report = None
    try:
        async for event in streaming_writer_node(state):
            yield event
            if '"step": "writer_done"' in event:
                try:
                    data = json.loads(event[6:])
                    final_report = data.get("report")
                except Exception:
                    pass
    except Exception as e:
        logger.error(f"[Workflow] Writer 节点异常: {e}")
        yield f"data: {json.dumps({'step': 'error', 'msg': f'Writer 写作节点异常: {str(e)}'})}\n\n"

    if final_report is None:
        final_report = {"标题": task, "调研概述": "报告生成失败（Writer 节点无返回）", "行业现状": "", "竞品分析": [], "机会与风险": {"机会": [], "风险": []}, "信息来源附录": []}

    # ===== 【修复3】会话提前创建：在 PDF 生成之前创建会话，确保素材池冻结 =====
    session_id = ""
    if create_session is not None:
        try:
            session_id = create_session(
                task=task,
                final_report=final_report,
                top_k_chunks=state.get("top_k_chunks", []),
                source_materials=state.get("source_materials", []),
                analyst_outline=state.get("analyst_outline", []),
                web_search_used=state.get("web_search_used", False),
            )
            logger.info(f"   💬 会话已创建（PDF 生成前）: {session_id}")
        except Exception as e:
            logger.warning(f"   ⚠️ 创建会话失败: {e}")

    # ---- Step 5: 生成 PDF ----
    yield f"data: {json.dumps({'step': 'pdf_generating', 'msg': '正在生成 PDF 报告...'})}\n\n"
    await asyncio.sleep(0.05)

    try:
        output_dir = os.path.join(tempfile.gettempdir(), "market_research_reports")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"report_{uuid.uuid4().hex}.pdf")
        generate_pdf_report(final_report, output_path)

        # ===== 【修复3】PDF 落地校验：检查文件是否存在且大小 > 0 =====
        if not os.path.exists(output_path):
            raise RuntimeError(f"PDF 文件未生成到磁盘: {output_path}")
        if os.path.getsize(output_path) == 0:
            raise RuntimeError(f"PDF 文件大小为 0: {output_path}")
        logger.info(f"   ✅ PDF 文件已落地校验: {output_path} ({os.path.getsize(output_path)} bytes)")

        yield f"data: {json.dumps({'step': 'done', 'report': final_report, 'pdf_url': f'/api/report/pdf?path={output_path}', 'pdf_path': output_path, 'session_id': session_id})}\n\n"
        _workflow_elapsed = __import__("time").time() - _workflow_start
        logger.info(f"✅ [Workflow] 流式工作流完成: 耗时={_workflow_elapsed:.2f}s")
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'PDF 生成失败: {str(e)}'})}\n\n"


async def run_followup_streaming_workflow(
    session_id: str,
    question: str,
    model_mode: str = "cloud",
) -> AsyncGenerator[str, None]:
    """
    追问模式流式工作流：
      - 从会话中获取冻结素材池和历史报告
      - 基于历史上下文 + 追问生成补充回答
      - 不重新检索、不修改原始报告
    """
    if get_session is None:
        yield f"data: {json.dumps({'step': 'error', 'msg': '会话管理器未初始化'})}\n\n"
        return

    session = get_session(session_id)
    if session is None:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'会话 {session_id} 不存在或已过期'})}\n\n"
        return

    yield f"data: {json.dumps({'step': 'followup_start', 'msg': '正在分析追问...'})}\n\n"
    await asyncio.sleep(0.05)

    # 构建上下文
    original_task = session.get("task", "")
    original_report = session.get("final_report", {})
    source_materials = session.get("source_materials", [])
    history = get_conversation_history(session_id)

    # 历史对话摘要（最近 6 轮）
    history_text_parts = []
    for h in history[-6:]:
        role_label = "用户" if h["role"] == "user" else "助手"
        history_text_parts.append(f"{role_label}: {h['content'][:300]}")
    history_text = "\n".join(history_text_parts) if history_text_parts else "（无历史对话）"
"    # ---- Step 4: Writer 流式生成报告 ----
    final_report = None
    try:
        async for event in streaming_writer_node(state):
            yield event
            if '\"step\": \"writer_done\"' in event:
                try:
                    data = json.loads(event[6:])
                    final_report = data.get(\"report\")
                except Exception:
                    pass
    except Exception as e:
        logger.error(f\"[Workflow] Writer 节点异常: {e}\")
        yield f\"data: {json.dumps({'step': 'error', 'msg': f'Writer 写作节点异常: {str(e)}'})}\\n\\n\"

    if final_report is None:
        final_report = {\"标题\": task, \"调研概述\": \"报告生成失败（Writer 节点无返回）\", \"行业现状\": \"\", \"竞品分析\": [], \"机会与风险\": {\"机会\": [], \"风险\": []}, \"信息来源附录\": []}"
    # 原始报告摘要
    report_summary = ""
    if isinstance(original_report, dict):
        title = original_report.get("标题", original_report.get("title", ""))
        overview = original_report.get("调研概述", original_report.get("overview", ""))
        industry = original_report.get("行业现状", original_report.get("industry_status", ""))
        competitors = original_report.get("竞品分析", original_report.get("competitor_analysis", []))
        opp_risk = original_report.get("机会与风险", original_report.get("opportunities_and_risks", {}))
        report_summary = f"标题: {title}\n调研概述: {overview[:200]}...\n"
        if industry:
            report_summary += f"行业现状: {industry[:200]}...\n"
        if competitors:
            names = [c.get("竞品名称", c.get("name", "?")) for c in competitors[:3] if isinstance(c, dict)]
            report_summary += f"竞品分析: {'; '.join(names)}\n"
        if opp_risk:
            opportunities = opp_risk.get("机会", opp_risk.get("opportunities", []))
            risks = opp_risk.get("风险", opp_risk.get("risks", []))
            report_summary += f"机会: {len(opportunities)}个, 风险: {len(risks)}个\n"

    # 素材概要
    materials_summary = ""
    for i, mat in enumerate(source_materials[:5]):
        text = mat.get("text", "")
        source_type = mat.get("source_type", "unknown")
        materials_summary += f"\n[素材{i+1} type={source_type}] {text[:200]}"

    # 记录用户追问
    if append_conversation:
        append_conversation(session_id, "user", question)

    llm = get_llm_streaming(temperature=0.3, model_mode=model_mode)

    system_prompt = (
        "你是一个专业市场研究分析助手。用户正在对之前生成的研报进行追问。\n\n"
        "【铁律】\n"
        "1. 你只能基于【原始素材库】和【历史报告】回答，严禁编造信息\n"
        "2. 如果素材或报告中找不到答案，明确说'您的问题在当前素材中缺乏足够信息，建议补充相关资料后再分析'\n"
        "3. 追问回答是追加性注释，不修改原始报告\n"
        "4. 回答应简洁、直达问题核心，控制在 300 字以内\n"
        "5. 引用素材时标注来源类型（PDF／网页）\n\n"
        "输出格式：纯文本段落（不要 JSON）"
    )

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            "原始研究课题：{task}\n\n"
            "【历史报告摘要】\n{report}\n\n"
            "【原始素材库（不可修改）】\n{materials}\n\n"
            "【历史对话】\n{history}\n\n"
            "用户追问：{question}\n\n"
            "请基于以上信息回答用户的追问。"
        ).format(
            task=original_task,
            report=report_summary,
            materials=materials_summary,
            history=history_text,
            question=question,
        )),
    ]

    full_answer = ""
    try:
        stream = llm.astream(prompt)
        while True:
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=_STREAM_TIMEOUT)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                logger.warning(f"[Followup] LLM 流式超时 ({_STREAM_TIMEOUT}s)，强制退出，防止节点悬停")
                break

            # ---- 检测流结束标记 ----
            if is_stream_finished(chunk):
                logger.debug("[Followup] 检测到流结束标记，退出循环")
                break

            text = extract_text_content(chunk)
            if text:
                full_answer += text
                yield f"data: {json.dumps({'step': 'followup_streaming', 'text': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'追问生成失败: {str(e)}'})}\n\n"
        return

    # 记录助手回答
    if append_conversation:
        append_conversation(session_id, "assistant", full_answer)

    yield f"data: {json.dumps({'step': 'followup_done', 'answer': full_answer})}\n\n"
