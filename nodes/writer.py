"""
第四阶段：受限写作节点（Writer）

SOP 规范：
  1. 严格遵守 Analyst 大纲逐节展开
  2. 证据（Evidence）字段必须逐字复制原始素材
  3. 详情（Details）部分进行因果分析、逻辑推演
  4. 形成"论点-证据-分析"完整闭环
"""

import asyncio
import json
from typing import Any, AsyncGenerator, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from agents.config import get_llm, get_llm_streaming
from agents.state import AgentState
from tools.logger import get_logger

logger = get_logger(__name__)

# ============================================================
#  流式推理超时配置（秒）
# ============================================================
_STREAM_TIMEOUT = 120  # 120 秒后强制退出循环，防止节点悬停
from prompts import get_prompt
import time
from tools.llm_utils import extract_text_content, is_stream_finished


def _build_materials_text(top_k_chunks: List[Dict]) -> str:
    """构建完整的素材文本（含来源类型标注）"""
    parts = []
    for chunk in top_k_chunks:
        if not isinstance(chunk, dict):
            chunk = {"text": str(chunk)}
        text = chunk.get("text", "")
        source_idx = chunk.get("source_index", -1)
        source_type = chunk.get("source_type", "unknown")
        trust_tier = chunk.get("trust_tier", "unverified")
        source_url = chunk.get("source_url", "")
        source_snippet = chunk.get("source_snippet", "")

        if source_type == "web":
            url_display = source_url[:80] if source_url else "?"
            source_label = f"[网络来源: {source_snippet[:30]}... | {url_display}]"
        else:
            source_label = "[PDF来源]"
        trust_note = f" trust={trust_tier}" if trust_tier != "verified" else ""

        parts.append(f"\n--- [素材来源 #{source_idx}] {source_label}{trust_note} ---\n{text}\n")

    return "".join(parts)


def _build_outline_desc(outline: List[Dict]) -> str:
    """构建大纲描述文本"""
    lines = []
    for section in outline:
        if not isinstance(section, dict):
            continue
        level = section.get("level", 1)
        indent = "  " * (level - 1)
        title = section.get("title", "")
        main_arg = section.get("main_argument", "")
        evidence = section.get("supporting_evidence", [])
        lines.append(f"{indent}- L{level}: {title}")
        if main_arg:
            lines.append(f"{indent}  论点: {main_arg}")
        if evidence:
            lines.append(f"{indent}  证据: {evidence}")
        for sub in section.get("subsections", []):
            if not isinstance(sub, dict):
                continue
            sub_level = sub.get("level", 2)
            sub_indent = "  " * (sub_level - 1)
            sub_title = sub.get("title", "")
            sub_arg = sub.get("argument", "")
            sub_ev = sub.get("evidence_indices", [])
            sub_plan = sub.get("paragraph_plan", "")
            lines.append(f"{sub_indent}- L{sub_level}: {sub_title}")
            if sub_arg:
                lines.append(f"{sub_indent}  论点: {sub_arg}")
            if sub_ev:
                lines.append(f"{sub_indent}  证据: {sub_ev}")
            if sub_plan:
                lines.append(f"{sub_indent}  段落规划: {sub_plan}")
    return "\n".join(lines)


def _build_args_desc(arguments: List[Dict]) -> str:
    """构建关键论点描述"""
    lines = []
    for i, arg in enumerate(arguments):
        if not isinstance(arg, dict):
            continue
        lines.append(f"论点{i+1}: {arg.get('argument', '')}")
        lines.append(f"  证据来源: {arg.get('evidence_indices', [])}")
        lines.append(f"  论述规划: {arg.get('paragraph_plan', '')}")
    return "\n".join(lines)


def _build_correction_note(fact_check_issues: List[Dict], report_version: int) -> str:
    """构建修正提示"""
    if not fact_check_issues:
        return ""
    brief_lines = []
    for issue in fact_check_issues[:5]:
        err_type = issue.get("error_type", issue.get("issue", ""))
        impact = issue.get("impact", "unknown")
        sentence = issue.get("sentence", "")[:60]
        suggestion = issue.get("suggestion", "")
        brief_lines.append(f"- [{impact}][{err_type}] {sentence} → {suggestion}")
    note = f"\n\n【需修正的问题（v{report_version} 核查结果）】\n" + "\n".join(brief_lines)
    if len(fact_check_issues) > 5:
        note += f"\n……还有 {len(fact_check_issues) - 5} 个问题，请一并修正"
    return note


def writer_node(state: AgentState):
    """
    受限写作节点（SOP 第四阶段）
    """
    task = state["task"]
    outline = state.get("analyst_outline", [])
    arguments = state.get("analyst_arguments", [])
    top_k_chunks = state.get("top_k_chunks", [])
    fact_check_issues = state.get("fact_check_issues", [])
    report_version = state.get("report_version", 0)

    logger.info(f"✍️ [Writer] 开始受限写作 (v{report_version})...")
    logger.info(f"   [Writer] 输入素材: {len(top_k_chunks)} 条, 大纲章节: {len(outline)} 个")
    _writer_start = __import__("time").time()

    all_materials_text = _build_materials_text(top_k_chunks)
    outline_desc = _build_outline_desc(outline)
    args_desc = _build_args_desc(arguments)
    correction_note = _build_correction_note(fact_check_issues, report_version)

    llm = get_llm(temperature=0.2, model_mode=state.get("model_mode"))

    system_prompt = get_prompt("system_prompt", "writer.yaml") + correction_note

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            "研究课题：%s\n\n"
            "【分析大纲（必须严格遵守）】\n%s\n\n"
            "【关键论点与证据索引】\n%s\n\n"
            "【原始素材（用于逐字复制证据）】\n%s\n\n"
            "请生成结构化分析报告。"
        ) % (task, outline_desc, args_desc, all_materials_text)),
    ]
    raw = llm.invoke(prompt)
    content = extract_text_content(raw)

    # 解析 JSON
    report_json = None
    try:
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            report_json = json.loads(content[start:end])
    except Exception:
        pass

    if report_json is None:
        report_json = {
            "标题": task,
            "调研概述": "报告生成失败，返回原始文本",
            "行业现状": "",
            "竞品分析": [],
            "机会与风险": {"机会": [], "风险": []},
            "信息来源附录": [],
        }

    logger.info(f"   ✅ Writer 报告生成完成: {len(report_json.get('竞品分析', []))} 个竞品分析")

    return {
        "final_report": report_json,
        "report_version": report_version + 1,
    }


async def streaming_writer_node(state: AgentState) -> AsyncGenerator[str, None]:
    """
    流式 Writer 节点：异步生成报告 JSON，实时 yield 进度事件。
    """
    task = state["task"]
    outline = state.get("analyst_outline", [])
    arguments = state.get("analyst_arguments", [])
    top_k_chunks = state.get("top_k_chunks", [])
    fact_check_issues = state.get("fact_check_issues", [])

    top_k_chunks = [
        c if isinstance(c, dict) else {"text": str(c), "source_index": i}
        for i, c in enumerate(top_k_chunks)
    ]
    yield f"data: {json.dumps({'step': 'writer_start', 'msg': '开始撰写报告...'})}\n\n"
    await asyncio.sleep(0.05)

    outline = [s for s in outline if isinstance(s, dict)]
    arguments = [a for a in arguments if isinstance(a, dict)]

    all_materials_text = _build_materials_text(top_k_chunks)
    outline_desc = _build_outline_desc(outline)
    args_desc = _build_args_desc(arguments)

    correction_note = ""
    if fact_check_issues:
        brief_lines = []
        for issue in fact_check_issues[:5]:
            sentence = issue.get("sentence", "")[:60]
            suggestion = issue.get("suggestion", "")
            brief_lines.append(f"- {sentence} → {suggestion}")
        correction_note = "\n\n【需修正的问题】\n" + "\n".join(brief_lines)

    llm = get_llm_streaming(temperature=0.2, model_mode=state.get("model_mode"))

    system_prompt = get_prompt("system_prompt", "writer.yaml") + correction_note

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            "研究课题：%s\n\n"
            "【分析大纲】\n%s\n\n"
            "【关键论点】\n%s\n\n"
            "【原始素材】\n%s\n\n"
            "请生成结构化分析报告。"
        ) % (task, outline_desc, args_desc, all_materials_text)),
    ]

    section_count = len([s for s in outline if isinstance(s, dict) and s.get('level', 1) == 1]) or 1
    full_content = ""
    try:
        stream = llm.astream(prompt)
        while True:
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=_STREAM_TIMEOUT)
            except StopAsyncIteration:
                break
            except asyncio.TimeoutError:
                logger.warning(f"[Writer] LLM 流式超时 ({_STREAM_TIMEOUT}s)，强制退出，防止节点悬停")
                break

            # ---- 检测流结束标记 ----
            if is_stream_finished(chunk):
                logger.debug("[Writer] 检测到流结束标记，退出循环")
                break

            text = extract_text_content(chunk)
            if text:
                full_content += text
                # 每 200 字符推送一次进度
                if len(full_content) % 200 < 20:
                    progress = min(len(full_content) // 800 + 1, section_count)
                    yield f"data: {json.dumps({'step': 'writer_streaming', 'text': text, 'progress': progress, 'total': max(section_count, 1)})}" + "\n\n"
                else:
                    yield f"data: {json.dumps({'step': 'writer_streaming', 'text': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'Writer 写作失败: {str(e)}'})}\n\n"
        return

    report_json = None
    try:
        if "{" in full_content:
            start = full_content.find("{")
            end = full_content.rfind("}") + 1
            report_json = json.loads(full_content[start:end])
    except Exception:
        pass

    if report_json is None:
        report_json = {"标题": task, "调研概述": "报告生成失败", "行业现状": "", "竞品分析": [], "机会与风险": {"机会": [], "风险": []}, "信息来源附录": []}

    yield f"data: {json.dumps({'step': 'writer_done', 'report': report_json})}\n\n"
