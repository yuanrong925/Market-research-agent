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
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm.provider import get_llm, get_llm_streaming
from core.utils.llm_utils import extract_text_content
from core.utils.logger import get_logger

from business.market_research.state import AgentState
from business.market_research.prompts import get_prompt
from business.market_research.utils.citation_manager import (
    build_citation_metadata,
    generate_conflict_alerts_section,
)

logger = get_logger(__name__)


def _build_material_text(
    top_k_chunks: List[Dict],
    citation_metadata: Optional[List[Dict]] = None,
    conflict_alerts: Optional[List[Dict]] = None,
) -> str:
    """构建精简素材文本 + 来源映射 + 引用元数据 + 冲突预警"""
    material_parts = []

    # 如果有冲突预警，先插入冲突说明
    if conflict_alerts:
        conflict_lines = ["【信源冲突说明】以下素材中存在信息冲突："]
        for c in conflict_alerts:
            topic = c.get("topic", "")
            pdf_stmt = c.get("pdf_statement", "")
            web_stmt = c.get("web_statement", "")
            if c.get("status") == "conflict":
                conflict_lines.append(
                    f"🔴 冲突主题「{topic}」：\n"
                    f"  📄【内部文档】{pdf_stmt[:100]}\n"
                    f"  🌐【公开网络】{web_stmt[:100]}\n"
                    f"  → 默认采信内部文档，同时备注外网不同观点"
                )
            else:
                conflict_lines.append(f"🟢 一致主题「{topic}」：信息一致")
        conflict_lines.append("---")
        material_parts.append("\n".join(conflict_lines))

    for i, chunk in enumerate(top_k_chunks):
        text = chunk.get("text", "")
        source_type = chunk.get("source_type", "unknown")
        trust_tier = chunk.get("trust_tier", "unverified")
        source_url = chunk.get("source_url", "")
        source_snippet = chunk.get("source_snippet", "")

        ref_id = f"S{i+1}"

        # 使用引用元数据（如有）
        cit_info = ""
        confidence_label = ""
        if citation_metadata and i < len(citation_metadata):
            cit = citation_metadata[i]
            confidence = cit.get("confidence_weight", 0.6)
            if source_type == "pdf":
                doc_name = cit.get("doc_name", "内部文档")
                page_num = cit.get("page_num", 0)
                page_str = f"，第{page_num}页" if page_num else ""
                confidence_label = "高置信度" if confidence >= 0.9 else "中置信度"
                cit_info = f"📄【内部文档信息】{doc_name}{page_str} | 置信权重: {confidence} ({confidence_label})"
            elif source_type == "web":
                url = cit.get("url", "")
                confidence_label = "中置信度" if confidence >= 0.6 else "低置信度"
                cit_info = f"🌐【公开网络信息】{url} | 置信权重: {confidence} ({confidence_label})"
                if trust_tier == "unverified":
                    cit_info += " | ⚠️ 未经验证，仅供交叉验证"
                elif trust_tier == "low_quality":
                    cit_info += " | ❌ 低质量来源，禁止引用"
        else:
            # 降级方案：使用原始信息
            if source_type == "web":
                url_display = source_url[:80] if source_url else "?"
                cit_info = f"[网络来源: {source_snippet[:30]}... | {url_display}]"
            else:
                cit_info = "[PDF来源]"

        trust_note = f" trust_tier={trust_tier}" if trust_tier != "verified" else ""
        material_parts.append(f"[{ref_id}] ({cit_info}{trust_note})\n{text[:1000]}")

    return "\n\n---\n\n".join(material_parts)


def analyst_node(state: AgentState):
    """
    分析与规划节点（SOP 第三阶段）
    """
    task = state["task"]
    top_k_chunks = state.get("top_k_chunks", [])
    citation_metadata = state.get("citation_metadata", [])
    conflict_alerts = state.get("conflict_alerts", [])

    logger.info("🧠 [Analyst] 开始分析与规划...")
    logger.info(f"   [Analyst] 输入素材数: {len(top_k_chunks)} 条")
    _analyst_start = __import__("time").time()
    material_text = _build_material_text(top_k_chunks, citation_metadata, conflict_alerts)

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
    logger.info(f"   [Analyst] 规划完成: {len(outline)} 章节, 耗时: {_analyst_elapsed:.2f}s")

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
    citation_metadata = state.get("citation_metadata", [])
    conflict_alerts = state.get("conflict_alerts", [])
    top_k_chunks = [
        c if isinstance(c, dict) else {"text": str(c), "source_index": i}
        for i, c in enumerate(top_k_chunks)
    ]

    yield f"data: {json.dumps({'step': 'analyst_start', 'msg': '开始分析规划...'})}\n\n"
    await asyncio.sleep(0.05)

    material_text = _build_material_text(top_k_chunks, citation_metadata, conflict_alerts)

    llm = get_llm_streaming(temperature=0.2, model_mode=state.get("model_mode"))

    system_prompt = get_prompt("system_prompt", "analyst_streaming.yaml")

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"研究课题：{task}\n\n参考素材：\n\n{material_text}\n\n请制定分析大纲。"),
    ]

    full_content = ""
    try:
        async for chunk in llm.astream(prompt):
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