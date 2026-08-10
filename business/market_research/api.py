"""
【市场调研专属】API 接口层

为 FastAPI 应用提供所有市场调研相关的 API 路由。
"""

import json
import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from core.llm.provider import get_llm, get_llm_streaming
from core.utils.logger import get_logger
from core.config import get_config

from business.market_research.state import AgentState, create_initial_state
from business.market_research.graph.graph import get_market_research_app as get_mr_graph
from business.market_research.graph.streaming import execute_streaming_workflow
from business.market_research.session_store import (
    create_session,
    get_session,
    append_conversation,
    get_conversation_history,
)

logger = get_logger(__name__)

# 创建 FastAPI 应用实例
app = FastAPI(
    title="Market Research Agent API",
    description="市场调研智能体 — 全自动研报生成系统",
    version="1.0.0",
)

router = APIRouter(prefix="/api/v1", tags=["market-research"])


# ============================================================
#  辅助函数：将对话历史格式化为自然语言
# ============================================================

def format_conversation(conversation: list, max_messages: int = 10) -> str:
    """将对话历史转为自然语言字符串，只保留最近 max_messages 条（约5轮对话）"""
    if not conversation:
        return "（暂无历史对话）"
    recent = conversation[-max_messages:] if len(conversation) > max_messages else conversation
    lines = []
    for msg in recent:
        role = "用户" if msg["role"] == "user" else "助手"
        content = msg["content"].strip()
        lines.append(f"{role}：{content}")
    return "\n".join(lines)


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "market-research-agent"}


# ============================================================
#  Ollama 模型管理接口
# ============================================================

@router.get("/ollama/models")
async def list_ollama_models():
    """从本地 Ollama 服务拉取可用模型列表"""
    import httpx
    cfg = get_config()
    base_url = cfg.ollama_base_url or "http://localhost:11434"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{base_url}/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                result = []
                for m in models:
                    name = m.get("name", "")
                    # 去掉 :latest 后缀
                    if name.endswith(":latest"):
                        name = name[:-7]
                    result.append({
                        "name": name,
                        "size": m.get("size", 0),
                        "modified": m.get("modified_at", ""),
                    })
                return {"models": result, "status": "ok"}
            else:
                return {"models": [], "status": "error", "message": f"Ollama 返回状态码 {resp.status_code}"}
    except Exception as e:
        logger.warning(f"拉取 Ollama 模型列表失败: {e}")
        return {"models": [], "status": "error", "message": str(e)}


# ============================================================
#  市场调研核心接口
# ============================================================

@router.post("/research")
async def run_research(
    task: str = Form(...),
    pdf_file: Optional[UploadFile] = File(None),
    model_mode: str = Form("cloud"),
    model_name: str = Form(""),
    manual_web_search_mode: str = Form("auto"),
):
    """
    执行市场调研 SOP 流程。

    参数:
      task: 研究任务描述
      pdf_file: 上传的 PDF 文件（可选）
      model_mode: 模型模式（cloud/local）
      model_name: 具体模型名称（如 qwen2.5:7b, local 模式下生效）
      manual_web_search_mode: 搜索模式（auto/enabled/disabled）
    """
    # 保存 PDF 文件
    pdf_path = ""
    if pdf_file:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        pdf_path = os.path.join(upload_dir, pdf_file.filename)
        with open(pdf_path, "wb") as f:
            content = await pdf_file.read()
            f.write(content)

    # 创建会话
    session_id = create_session(task=task)

    # 初始化状态
    state = create_initial_state(
        task=task,
        pdf_path=pdf_path,
        model_mode=model_mode,
        model_name=model_name,
        manual_web_search_mode=manual_web_search_mode,
    )

    # 执行工作流
    mr_graph = get_mr_graph()
    result = mr_graph.invoke(state)

    # 更新会话
    session = get_session(session_id)
    if session:
        session["final_report"] = result.get("final_report", {})
        session["top_k_chunks"] = result.get("top_k_chunks", [])
        session["source_materials"] = result.get("source_materials", [])
        session["web_search_used"] = result.get("web_search_used", False)

    return {
        "session_id": session_id,
        "report": result.get("final_report", {}),
        "fact_check_passed": result.get("fact_check_passed", False),
        "web_search_used": result.get("web_search_used", False),
        "circuit_breaker_triggered": result.get("circuit_breaker_triggered", False),
    }


@router.post("/research/stream")
async def run_research_stream(
    task: str = Form(...),
    pdf_file: Optional[UploadFile] = File(None),
    model_mode: str = Form("cloud"),
    model_name: str = Form(""),
    manual_web_search_mode: str = Form("auto"),
):
    """
    流式执行市场调研 SOP 流程。
    返回 SSE 事件流，实时推送进度。
    """
    pdf_path = ""
    if pdf_file:
        upload_dir = "uploads"
        os.makedirs(upload_dir, exist_ok=True)
        pdf_path = os.path.join(upload_dir, pdf_file.filename or "")
        with open(pdf_path, "wb") as f:
            content = await pdf_file.read()
            f.write(content)
    session_id = create_session(task=task)

    async def event_stream():
        # streaming.py 内部已包含 done 事件，这里只需要透传
        async for event in execute_streaming_workflow(
            task=task,
            pdf_path=pdf_path,
            model_mode=model_mode,
            model_name=model_name,
            manual_web_search_mode=manual_web_search_mode,
            session_id=session_id,
        ):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/research/follow-up")
async def follow_up_question(
    session_id: str = Form(...),
    question: str = Form(...),
    model_name: str = Form(""),
):
    """
    追问接口：基于已有会话上下文回答追问。

    追问不修改原始报告，不重新检索，仅基于已有素材生成补充回答。
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    # 追加用户问题
    append_conversation(session_id, "user", question)

    # 构建上下文（素材 + 历史报告 + 对话记录）
    context = {
        "task": session["task"],
        "report": session["final_report"],
        "materials": session["source_materials"],
        "conversation": session["conversation"],
    }

    # 将对话历史格式化为自然语言（最近5轮，最多10条）
    history_text = format_conversation(context["conversation"])

    # 生成回答
    llm = get_llm(temperature=0.2, model_name=model_name)
    response = llm.invoke(
        f"基于以下上下文回答用户的问题。\n\n"
        f"原始任务：{context['task']}\n\n"
        f"已生成的报告摘要：{json.dumps(context['report'], ensure_ascii=False)[:2000]}\n\n"
        f"对话历史：\n{history_text}\n\n"
        f"用户问题：{question}\n\n"
        f"请基于已有信息给出回答，如果信息不足，请说明。"
    )

    answer = getattr(response, "content", str(response))
    append_conversation(session_id, "assistant", answer)

    return {
        "session_id": session_id,
        "answer": answer,
    }


@router.get("/session/{session_id}")
async def get_session_info(session_id: str):
    """获取会话信息"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {
        "session_id": session_id,
        "task": session["task"],
        "has_report": bool(session.get("final_report")),
        "conversation_count": len(session.get("conversation", [])),
        "web_search_used": session.get("web_search_used", False),
    }


@router.get("/conversation/{session_id}")
async def get_conversation(session_id: str):
    """获取会话对话历史"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {
        "session_id": session_id,
        "conversation": session.get("conversation", []),
        "count": len(session.get("conversation", [])),
    }


@router.get("/report/{session_id}")
async def get_report(session_id: str):
    """获取会话的报告"""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")
    return {
        "session_id": session_id,
        "report": session.get("final_report", {}),
    }


# ============================================================
#  注册路由、静态文件与前端入口
# ============================================================

app.include_router(router)

# 静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# 模板目录
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
INDEX_PATH = os.path.join(TEMPLATES_DIR, "index.html")


@app.get("/")
async def serve_index():
    """提供前端页面"""
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content)
    return {"message": "Market Research Agent API", "docs": "/docs"}


@app.post("/api/report/pdf")
async def frontend_report_pdf(
    task: str = Form(...),
    report_text: str = Form(...),
):
    """前端兼容：POST /api/report/pdf → 生成 PDF 下载"""
    try:
        report_data = json.loads(report_text)
    except json.JSONDecodeError:
        report_data = {"标题": task, "摘要": report_text}

    import tempfile, uuid
    output_dir = os.path.join(tempfile.gettempdir(), "market_research_reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"report_{uuid.uuid4().hex}.pdf")

    from agents.retrieval.pdf_report import generate_frontend_pdf
    generate_frontend_pdf(report_data, task, output_path)

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise HTTPException(status_code=500, detail="PDF 生成失败")

    return StreamingResponse(
        open(output_path, "rb"),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=market_research_report.pdf"},
    )


# ============================================================
#  前端兼容路由（app.js 直接调用的路径）
# ============================================================


@app.post("/api/followup-stream")
async def frontend_followup_stream(
    session_id: str = Form(...),
    question: str = Form(...),
    model_mode: str = Form("cloud"),
    model_name: str = Form(""),
):
    """
    前端兼容：POST /api/followup-stream → SSE 流式推送追问回答
    """
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或已过期")

    append_conversation(session_id, "user", question)

    context = {
        "task": session["task"],
        "report": session["final_report"],
        "materials": session["source_materials"],
        "conversation": session["conversation"],
    }

    # 将对话历史格式化为自然语言（最近5轮，最多10条）
    history_text = format_conversation(context["conversation"])

    async def event_stream():
        try:
            llm = get_llm_streaming(temperature=0.2, model_mode=model_mode, model_name=model_name)
            prompt = (
                f"基于以下上下文回答用户的问题。\n\n"
                f"原始任务：{context['task']}\n\n"
                f"已生成的报告摘要：{json.dumps(context['report'], ensure_ascii=False)[:2000]}\n\n"
                f"对话历史：\n{history_text}\n\n"
                f"用户问题：{question}\n\n"
                f"请基于已有信息给出回答，如果信息不足，请说明。"
            )

            accumulated = ""
            async for chunk in llm.astream(prompt):
                token = chunk.content if hasattr(chunk, 'content') else str(chunk)
                if token:
                    accumulated += token
                    event_data = json.dumps({"text": token}, ensure_ascii=False)
                    yield f"data: {event_data}\n\n"

            append_conversation(session_id, "assistant", accumulated)

            done_data = json.dumps({
                "step": "followup_done",
                "answer": accumulated,
            }, ensure_ascii=False)
            yield f"data: {done_data}\n\n"

        except Exception as e:
            logger.error(f"[追问] 流式错误: {e}")
            error_data = json.dumps({
                "step": "error",
                "msg": str(e),
            }, ensure_ascii=False)
            yield f"data: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
