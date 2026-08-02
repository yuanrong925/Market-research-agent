"""
第三阶段：分析与规划节点（Analyst）

SOP 规范：
  1. 分析师仅阅读 Top-K 高相关片段
  2. 生成结构化大纲（多级标题）
  3. 提取关键论点
  4. 每个论点标注证据索引（Source Index）
"""

import asyncio
import json
import time
from typing import Any, AsyncGenerator, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agents.config import get_llm, get_llm_streaming
from agents.state import AgentState
from tools.logger import get_logger

logger = get_logger(__name__)
from prompts import get_prompt
from tools.llm_utils import extract_text_content, is_stream_finished

# ============================================================
#  流式推理超时配置（秒）
# ============================================================
_STREAM_TIMEOUT = 120  # 120 秒后强制退出循环，防止节点悬停


def _build_material_text(top_k_chunks: List[Dict]) -> str:
    """构建精简素材文本 + 来源映射"""
    material_text_parts = []
    for i, chunk in enumerate(top_k_chunks):
        text = chunk.get("text", "")
        source_idx = chunk.get("source_index", i)
        source_type = chunk.get("source_type", "unknown")
        trust_tier = chunk.get("trust_tier", "unverified")
        source_url = chunk.get("source_url", "")
        source_snippet = chunk.get("source_snippet", "")

        ref_id = f"S{i+1}"
        if source_type == "web":
            url_display = source_url[:80] if source_url else "?"
            source_label = f"[网络来源: {source_snippet[:30]}... | {url_display}]"
        else:
            source_label = "[PDF来源]"
        trust_note = f" trust={trust_tier}" if trust_tier != "verified" else ""

        material_text_parts.append(f"[{ref_id}] ({source_label}{trust_note})\n{text[:1000]}")

    return "\n\n---\n\n".join(material_text_parts)


def analyst_node(state: AgentState):
    """
    分析与规划节点（SOP 第三阶段）
    """
    task = state["task"]
    top_k_chunks = state.get("top_k_chunks", [])

    logger.info("🧠 [Analyst] 开始分析与规划...")
    logger.info(f"   [Analyst] 输入素材数: {len(top_k_chunks)} 条")
    _analyst_start = __import__("time").time()
    material_text = _build_material_text(top_k_chunks)

    llm = get_llm(temperature=0.2, model_mode=state.get("model_mode"))

    system_prompt = get_prompt("system_prompt", "analyst.yaml")

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"研究课题：{task}\n\n参考素材（每个片段前有引用编号 [S1], [S2]...）：\n\n{material_text}\n\n请制定分析大纲。"
        ),
    ]
    resp = llm.invoke(prompt)
    content = extract_text_content(resp)

    # 解析 JSON
    outline = None
    arguments = []
    report_title = task

    try:
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            data = json.loads(content[start:end])
            outline = data.get("sections", [])
            arguments = data.get("key_arguments", [])
            report_title = data.get("title", task)
    except Exception as exc:
        logger.warning(f"   ⚠️ Analyst 大纲解析失败: {exc}")
        outline = [
            {
                "level": 1, "title": "概述",
                "main_argument": f"关于'{task}'的总体分析",
                "supporting_evidence": [], "subsections": [],
            },
            {
                "level": 1, "title": "核心分析",
                "main_argument": "深入分析",
                "supporting_evidence": [],
                "subsections": [
                    {
                        "level": 2, "title": "关键发现",
                        "argument": "主要发现",
                        "evidence_indices": [],
                        "paragraph_plan": "列举关键发现并引用证据",
                    }
                ],
            },
            {
                "level": 1, "title": "结论与建议",
                "main_argument": "总结与建议",
                "supporting_evidence": [], "subsections": [],
            },
        ]
        arguments = [
            {"argument": "基于素材的综合分析", "evidence_indices": [], "paragraph_plan": "综合论述"}
        ]

    _analyst_elapsed = __import__("time").time() - _analyst_start
    total_chars = sum(len(s.get("title", "")) for s in outline)
    logger.info(f"   [Analyst] 规划完成: {len(outline)} 章节, {len(arguments)} 论点, 总字数: {total_chars}, 耗时: {_analyst_elapsed:.2f}s")

    return {
        "analyst_outline": outline,
        "analyst_arguments": arguments,
    }


async def streaming_analyst_node(state: AgentState) -> AsyncGenerator[str, None]:
    """
    流式 Analyst 节点：异步生成大纲 JSON，实时 yield 进度事件。
    """
    task = state["task"]
    top_k_chunks = state.get("top_k_chunks", [])
    top_k_chunks = [
        c if isinstance(c, dict) else {"text": str(c), "source_index": i}
        for i, c in enumerate(top_k_chunks)
    ]

    yield f"data: {json.dumps({'step': 'analyst_start', 'msg': '开始分析规划...'})}\n\n"
    await asyncio.sleep(0.05)

    material_text = _build_material_text(top_k_chunks)

    llm = get_llm_streaming(temperature=0.2, model_mode=state.get("model_mode"))

    system_prompt = get_prompt("system_prompt", "analyst_streaming.yaml")

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"研究课题：{task}\n\n参考素材：\n\n{material_text}\n\n请制定分析大纲。"),
    ]

    full_content = ""
    try:
        stream = llm.astream(prompt)
        while True:
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=_STREAM_TIMEOUT)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                logger.warning(f"[Analyst] LLM 流式超时 ({_STREAM_TIMEOUT}s)，强制退出，防止节点悬停")
                break

            # ---- 检测流结束标记 ----
            if is_stream_finished(chunk):
                logger.debug("[Analyst] 检测到流结束标记，退出循环")
                break

            text = extract_text_content(chunk)
            if text:
                full_content += text
                yield f"data: {json.dumps({'step': 'analyst_streaming', 'text': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'Analyst 分析失败: {str(e)}'})}\n\n"
        return

    outline = None
    arguments = []
    report_title = task
    try:
        if "{" in full_content:
            start = full_content.find("{")
            end = full_content.rfind("}") + 1
            data = json.loads(full_content[start:end])
            outline = data.get("sections", [])
            arguments = data.get("key_arguments", [])
            report_title = data.get("title", task)
    except Exception:
        pass

    result = {
        "analyst_outline": outline or [],
        "analyst_arguments": arguments,
        "report_title": report_title,
    }
    yield f"data: {json.dumps({'step': 'analyst_done', 'result': result})}\n\n"
