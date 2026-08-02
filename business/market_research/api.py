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

from core.llm.provider import get_llm
from core.utils.logger import get_logger

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


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "market-research-agent"}


@router.post("/research")
async def run_research(
    task: str = Form(...),
    pdf_file: Optional[UploadFile] = File(None),
    model_mode: str = Form("cloud"),
    manual_web_search_mode: str = Form("auto"),
):
    """
    执行市场调研 SOP 流程。

    参数:
      task: 研究任务描述
      pdf_file: 上传的 PDF 文件（可选）
      model_mode: 模型模式（cloud/local）
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
        # 推送每一步实时日志
        async for event in execute_streaming_workflow(
            task=task,
            pdf_path=pdf_path,
            model_mode=model_mode,
            manual_web_search_mode=manual_web_search_mode,
            session_id=session_id,
        ):
            yield event
        
        # 流程全部跑完，推送携带完整报告的结束事件
        # 读取当前会话存储的完整报告
        session_info = get_session(session_id)
        final_report = session_info.get("final_report", {})
        # 构造前端识别的complete消息，SSE标准格式
        complete_data = json.dumps({
            "step": "complete",
            "msg": "全部分析完成！",
            "final_report": final_report,
            "session_id": session_id,
        }, ensure_ascii=False)
        yield f"data: {complete_data}\n\n"

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

    # 生成回答
    llm = get_llm(temperature=0.2)
    response = llm.invoke(
        f"基于以下上下文回答用户的问题。\n\n"
        f"原始任务：{context['task']}\n\n"
        f"已生成的报告摘要：{json.dumps(context['report'], ensure_ascii=False)[:2000]}\n\n"
        f"对话历史：{json.dumps(context['conversation'][-5:], ensure_ascii=False)}\n\n"
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
    """前端兼容：POST /api/report/pdf → 生成 PDF 下载（使用 reportlab 直接生成，无外部依赖）"""
    try:
        report_data = json.loads(report_text)
    except json.JSONDecodeError:
        report_data = {"标题": task, "摘要": report_text}

    import tempfile, uuid
    output_dir = os.path.join(tempfile.gettempdir(), "market_research_reports")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"report_{uuid.uuid4().hex}.pdf")

    # 使用 reportlab 直接生成 PDF，无需 agents.retrieval.rag 依赖
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4
    margin = 25 * mm
    y = height - margin
    line_height = 5 * mm

    def draw_line(text, x, y, font="Helvetica", size=10):
        nonlocal c
        c.setFont(font, size)
        c.drawString(x, y, text)
        return y - line_height

    # 标题
    title = report_data.get("title") or report_data.get("标题") or task
    y = draw_line(title, margin, y, "Helvetica-Bold", 16)
    y -= line_height * 2

    # 1. 调研概述
    overview = report_data.get("overview") or report_data.get("调研概述") or ""
    if overview:
        y = draw_line("1. 调研概述", margin, y, "Helvetica-Bold", 12)
        y -= 2
        words = str(overview).split()
        line = ""
        for word in words:
            test = line + word + " "
            if c.stringWidth(test, "Helvetica", 10) < width - 2 * margin:
                line = test
            else:
                y = draw_line(line, margin, y, "Helvetica", 10)
                line = word + " "
        if line.strip():
            y = draw_line(line, margin, y, "Helvetica", 10)
        y -= line_height

    # 2. 行业现状
    industry = report_data.get("industry_status") or report_data.get("行业现状") or ""
    if industry:
        y -= line_height
        y = draw_line("2. 行业现状", margin, y, "Helvetica-Bold", 12)
        y -= 2
        words = str(industry).split()
        line = ""
        for word in words:
            test = line + word + " "
            if c.stringWidth(test, "Helvetica", 10) < width - 2 * margin:
                line = test
            else:
                y = draw_line(line, margin, y, "Helvetica", 10)
                line = word + " "
        if line.strip():
            y = draw_line(line, margin, y, "Helvetica", 10)
        y -= line_height

    # 3. 竞品分析
    competitors = report_data.get("competitor_analysis") or report_data.get("竞品分析") or []
    if competitors:
        y -= line_height
        y = draw_line("3. 竞品分析", margin, y, "Helvetica-Bold", 12)
        y -= 2
        for c_item in competitors:
            name = c_item.get("name") or c_item.get("竞品名称") or ""
            analysis = c_item.get("analysis") or c_item.get("分析") or ""
            if name:
                y = draw_line(f"• {name}", margin, y, "Helvetica-Bold", 10)
            if analysis:
                y = draw_line(f"  {analysis}", margin + 10, y, "Helvetica", 10)
            y -= 4
            if y < margin:
                c.showPage()
                y = height - margin

    # 4. 机会与风险
    opp_risk = report_data.get("opportunities_and_risks") or report_data.get("机会与风险") or {}
    opportunities = opp_risk.get("opportunities") or opp_risk.get("机会") or []
    risks = opp_risk.get("risks") or opp_risk.get("风险") or []
    if opportunities or risks:
        y -= line_height
        y = draw_line("4. 机会与风险", margin, y, "Helvetica-Bold", 12)
        y -= 2
        if opportunities:
            y = draw_line("机会:", margin, y, "Helvetica-Bold", 10)
            for opp in opportunities:
                y = draw_line(f"  • {opp}", margin, y, "Helvetica", 10)
                y -= 3
                if y < margin:
                    c.showPage()
                    y = height - margin
        if risks:
            y = draw_line("风险:", margin, y, "Helvetica-Bold", 10)
            for r in risks:
                y = draw_line(f"  • {r}", margin, y, "Helvetica", 10)
                y -= 3
                if y < margin:
                    c.showPage()
                    y = height - margin

    # 5. 信息来源附录
    sources = report_data.get("sources_appendix") or report_data.get("信息来源附录") or []
    if sources:
        y -= line_height
        y = draw_line("5. 信息来源附录", margin, y, "Helvetica-Bold", 12)
        y -= 2
        for i, ref in enumerate(sources):
            y = draw_line(f"  [{i+1}] {ref}", margin, y, "Helvetica", 9)
            y -= 3
            if y < margin:
                c.showPage()
                y = height - margin

    c.save()

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
):
    """前端兼容：POST /api/followup-stream → 转发到 follow_up_question"""
    return await follow_up_question(
        session_id=session_id,
        question=question,
    )
