"""
第四阶段：受限写作节点（Writer）

SOP 规范：
  1. 严格遵守 Analyst 输出的分析大纲
  2. 证据字段必须逐字复制原始素材原文
  3. 使用 Markdown 角标引用格式 [1][2]
  4. 文末自动生成参考文献清单
  5. 冲突场景同时呈现两种观点
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
    detect_conflicts,
    generate_references_section,
    generate_conflict_alerts_section,
)
from business.market_research.utils.material_utils import classify_trust_tier
from business.market_research.utils.constants import PDF_ONLY_WRITER_CONSTRAINT

logger = get_logger(__name__)


def _prepare_material_with_citations(
    top_k_chunks: List[Dict],
    source_materials: List[Dict],
    citation_metadata: List[Dict],
    conflict_alerts: List[Dict],
    pdf_only: bool = False,
) -> str:
    """
    构建带引用编号的素材文本，供 Writer LLM 使用。

    每条素材前标注引用编号 [S1], [S2]... 和对应的引用元数据，
    包括来源类型、置信权重、文档名/链接等。
    """
    material_parts = []

    # 如果有冲突预警，先插入冲突说明
    if conflict_alerts:
        conflict_lines = ["【信源冲突说明】以下素材中存在信息冲突："]
        for c in conflict_alerts:
            topic = c.get("topic", "")
            pdf_stmt = c.get("pdf_statement", "")
            web_stmt = c.get("web_statement", "")
            resolution = c.get("resolution", "")
            if c.get("status") == "conflict":
                conflict_lines.append(
                    f"🔴 冲突主题「{topic}」：\n"
                    f"  📄【内部文档】{pdf_stmt}\n"
                    f"  🌐【公开网络】{web_stmt}\n"
                    f"  ⚖️ 处理：{resolution}"
                )
            else:
                conflict_lines.append(
                    f"🟢 一致主题「{topic}」：{pdf_stmt}"
                )
        conflict_lines.append("---")
        material_parts.append("\n".join(conflict_lines))

    # 构建每条素材的引用信息
    for i, item in enumerate(top_k_chunks):
        text = item.get("text", "")
        source_type = item.get("source_type", "unknown")
        trust_tier = item.get("trust_tier", "unverified")

        # 查找对应的引用元数据
        ref_id = f"S{i + 1}"
        cit_info = ""
        if i < len(citation_metadata):
            cit = citation_metadata[i]
            confidence = cit.get("confidence_weight", 0.6)

            # pdf_only 模式下，所有来源统一显示为文档资料
            effective_source_type = source_type
            if pdf_only:
                effective_source_type = "pdf"

            if effective_source_type == "pdf":
                doc_name = cit.get("doc_name", "内部文档")
                page_num = cit.get("page_num", 0)
                page_str = f"，第{page_num}页" if page_num else ""
                confidence_label = "高置信度" if confidence >= 0.9 else "中置信度"
                cit_info = (
                    f"📄【文档资料】{doc_name}{page_str} | "
                    f"置信权重: {confidence} ({confidence_label})"
                )
            elif source_type == "web":
                url = cit.get("url", "")
                confidence_label = "中置信度" if confidence >= 0.6 else "低置信度"
                cit_info = (
                    f"🌐【公开网络信息】{url} | "
                    f"置信权重: {confidence} ({confidence_label})"
                )
                if trust_tier == "unverified":
                    cit_info += " | ⚠️ 未经验证，仅供交叉验证"
                elif trust_tier == "low_quality":
                    cit_info += " | ❌ 低质量来源，禁止引用"

        trust_note = f" trust_tier={trust_tier}" if trust_tier != "verified" else ""
        material_parts.append(
            f"[{ref_id}] ({cit_info}{trust_note})\n{text[:1200]}"
        )

    return "\n\n---\n\n".join(material_parts)


def _build_outline_text(outline: List[Dict]) -> str:
    """构建大纲文本"""
    lines = []
    for section in outline:
        level = section.get("level", 1)
        title = section.get("title", "")
        main_arg = section.get("main_argument", "")
        evidence = section.get("supporting_evidence", [])
        indent = "  " * (level - 1)
        ev_str = f" [证据: {', '.join(evidence)}]" if evidence else ""
        lines.append(f"{indent}【{'=' * (3 - level)} {title} {'=' * (3 - level)}】{ev_str}")
        if main_arg:
            lines.append(f"{indent}  核心论点: {main_arg}")
        for sub in section.get("subsections", []):
            sub_level = sub.get("level", 2)
            sub_title = sub.get("title", "")
            sub_arg = sub.get("argument", "")
            sub_ev = sub.get("evidence_indices", [])
            sub_indent = "  " * (sub_level - 1)
            sub_ev_str = f" [证据: {', '.join(sub_ev)}]" if sub_ev else ""
            lines.append(f"{sub_indent}- {sub_title}{sub_ev_str}")
            if sub_arg:
                lines.append(f"{sub_indent}  论点: {sub_arg}")
            pp = sub.get("paragraph_plan", "")
            if pp:
                lines.append(f"{sub_indent}  段落规划: {pp}")
    return "\n".join(lines)


def writer_node(state: AgentState):
    """
    受限写作节点（SOP 第四阶段）

    根据 Analyst 大纲 + 带引用编号的素材，生成带角标引用的报告。
    """
    task = state.get("task", "")
    outline = state.get("analyst_outline", [])
    arguments = state.get("analyst_arguments", [])
    top_k_chunks = state.get("top_k_chunks", [])
    source_materials = state.get("source_materials", [])
    model_mode = state.get("model_mode", "cloud")
    conflict_alerts = state.get("conflict_alerts", [])

    # ===== 检测 pdf_only 模式 =====
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    pdf_only = manual_mode in ("disabled", "pdf_only")
    if pdf_only:
        logger.info("   [Writer] 检测到仅 PDF 模式，将追加约束：所有来源只能标记为文档资料")

    logger.info("✍️ [Writer] 开始受限写作...")
    logger.info(f"   [Writer] 大纲章节: {len(outline)}, 素材数: {len(top_k_chunks)}")
    _writer_start = __import__("time").time()

    # Step 1: 生成/获取引用元数据
    citation_metadata = state.get("citation_metadata", [])
    if not citation_metadata and source_materials:
        citation_metadata = build_citation_metadata(source_materials, pdf_only=pdf_only)
        logger.info(f"   [Writer] 生成 {len(citation_metadata)} 条引用元数据")

    # Step 2: 检测冲突（如果尚未检测）
    if not conflict_alerts and len(top_k_chunks) > 0:
        pdf_materials = [c for c in top_k_chunks if c.get("source_type") == "pdf"]
        web_materials = [c for c in top_k_chunks if c.get("source_type") == "web"]
        if pdf_materials and web_materials:
            conflict_alerts = detect_conflicts(pdf_materials, web_materials, citation_metadata, pdf_only=pdf_only)
            if conflict_alerts:
                logger.warning(f"   ⚠️ [Writer] 检测到 {len(conflict_alerts)} 处信息冲突")

    # Step 3: 构建带引用编号的素材文本
    material_text = _prepare_material_with_citations(
        top_k_chunks, source_materials, citation_metadata, conflict_alerts, pdf_only=pdf_only
    )

    # Step 4: 构建大纲文本
    outline_text = _build_outline_text(outline)

    # Step 5: 构建结构化提示
    llm = get_llm(temperature=0.2, model_mode=model_mode)
    system_prompt = get_prompt("system_prompt", "writer.yaml")

    # 构建冲突上下文（如有）
    conflict_context = ""
    if conflict_alerts:
        conflict_context = "\n\n【信源冲突处理规则】\n"
        conflict_context += "以下素材中存在信息冲突，请严格按照以下规则处理：\n"
        for c in conflict_alerts:
            if c.get("status") == "conflict":
                conflict_context += (
                    f"- 主题「{c['topic']}」：\n"
                    f"  📄【内部文档】观点: {c['pdf_statement'][:100]}...\n"
                    f"  🌐【公开网络】观点: {c['web_statement'][:100]}...\n"
                    f"  → 默认采信内部文档，同时备注外网不同观点\n"
                )

    # 构建多源数据冲突报告（如有）
    data_conflicts = state.get("data_conflicts", [])
    data_conflict_report = ""
    if data_conflicts:
        conflict_items = [c for c in data_conflicts if c.get("status") == "conflict"]
        if conflict_items:
            data_conflict_report = "\n\n【多源数据冲突报告】以下为数据冲突项，请按【数据冲突高亮规则】处理：\n"
            for c in conflict_items:
                data_conflict_report += (
                    f"- {c['label']}: "
                    f"PDF={c['pdf_value']}{c['pdf_unit']} (来源: {c.get('pdf_source', '内部文档')}) vs "
                    f"Web={c['web_value']}{c['web_unit']} (来源: {c.get('web_source', '公开网络')})\n"
                    f"  差异率: {c['diff_ratio'] * 100:.1f}% 需标记【待人工确认】\n"
                )
            logger.info(f"   📋 [Writer] 注入 {len(conflict_items)} 条数据冲突报告")

    # 构建引用元数据说明
    citation_context = "\n\n【引用元数据说明】\n"
    citation_context += "每条素材前的引用信息包含：\n"
    citation_context += "- 引用编号 [S1], [S2]...\n"
    citation_context += "- 📄【内部文档信息】= 文档名 + 页码\n"
    citation_context += "- 🌐【公开网络信息】= 网页链接\n"
    citation_context += "- 置信权重: 0.9=高(内部文档), 0.6=中(外网资讯)\n"
    citation_context += "\n在报告正文中使用 [1][2] 格式角标引用，文末参考文献由系统自动生成，无需手动添加。\n"

        # pdf_only 模式下追加来源标注约束（使用全局常量）
    pdf_only_constraint = f"\n\n{PDF_ONLY_WRITER_CONSTRAINT}" if pdf_only else ""

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"研究课题：{task}\n\n"
                f"【分析大纲】\n{outline_text}\n\n"
                f"【关键论点】\n{json.dumps(arguments, ensure_ascii=False, indent=2)[:2000]}\n\n"
                f"【引用素材】（每条素材前标注了引用编号 [S1], [S2]... 和引用元数据）\n\n"
                f"{material_text}\n"
                f"{data_conflict_report}"
                f"{conflict_context}"
                f"{citation_context}"
                f"{pdf_only_constraint}"
                f"\n请严格按照大纲结构撰写研报。"
            )
        ),
    ]

    resp = llm.invoke(prompt)
    content = extract_text_content(resp)

    # Step 6: 解析 JSON 输出
    report = {}
    try:
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            report = json.loads(content[start:end])
    except Exception as exc:
        logger.warning(f"   ⚠️ Writer 输出解析失败: {exc}")
        report = {"标题": task, "摘要": "报告生成失败，请重试", "关键发现": []}

    # Step 7: 生成参考文献清单
    references_section = generate_references_section(citation_metadata, pdf_only=pdf_only)

    # Step 8: 生成冲突预警章节
    conflict_alerts_section = generate_conflict_alerts_section(conflict_alerts)

    _writer_elapsed = __import__("time").time() - _writer_start
    logger.info(f"   ✅ [Writer] 写作完成: {report.get('标题', '')[:40]}..., 耗时: {_writer_elapsed:.2f}s")

    return {
        "final_report": report,
        "report_version": state.get("report_version", 0) + 1,
        "citation_metadata": citation_metadata,
        "conflict_alerts": conflict_alerts,
        "references_section": references_section,
        "report_with_citations": json.dumps(report, ensure_ascii=False),
    }


async def streaming_writer_node(state: AgentState) -> AsyncGenerator[str, None]:
    """
    流式 Writer 节点：异步生成报告，实时 yield 进度事件。
    """
    task = state.get("task", "")
    outline = state.get("analyst_outline", [])
    arguments = state.get("analyst_arguments", [])
    top_k_chunks = state.get("top_k_chunks", [])
    source_materials = state.get("source_materials", [])
    model_mode = state.get("model_mode", "cloud")
    conflict_alerts = state.get("conflict_alerts", [])

    # ===== 检测 pdf_only 模式 =====
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    pdf_only = manual_mode in ("disabled", "pdf_only")

    yield f"data: {json.dumps({'step': 'writer_start', 'msg': '✍️ 开始撰写研报...'})}\n\n"
    await asyncio.sleep(0.05)

    # Step 1: 生成引用元数据
    citation_metadata = state.get("citation_metadata", [])
    if not citation_metadata and source_materials:
        citation_metadata = build_citation_metadata(source_materials, pdf_only=pdf_only)

    # Step 2: 检测冲突
    if not conflict_alerts and len(top_k_chunks) > 0:
        pdf_materials = [c for c in top_k_chunks if c.get("source_type") == "pdf"]
        web_materials = [c for c in top_k_chunks if c.get("source_type") == "web"]
        if pdf_materials and web_materials:
            conflict_alerts = detect_conflicts(pdf_materials, web_materials, citation_metadata, pdf_only=pdf_only)
            if conflict_alerts:
                yield f"data: {json.dumps({'step': 'writer_conflict', 'msg': f'⚠️ 检测到 {len(conflict_alerts)} 处信息冲突', 'conflict_alerts': conflict_alerts})}\n\n"
                await asyncio.sleep(0.1)

    # Step 3: 构建素材文本
    material_text = _prepare_material_with_citations(
        top_k_chunks, source_materials, citation_metadata, conflict_alerts, pdf_only=pdf_only
    )
    outline_text = _build_outline_text(outline)

    # Step 4: 流式调用 LLM
    llm = get_llm_streaming(temperature=0.2, model_mode=model_mode)
    system_prompt = get_prompt("system_prompt", "writer.yaml")

    # 构建多源数据冲突报告（如有）
    data_conflicts = state.get("data_conflicts", [])
    data_conflict_report = ""
    if data_conflicts:
        conflict_items = [c for c in data_conflicts if c.get("status") == "conflict"]
        if conflict_items:
            data_conflict_report = "\n\n【多源数据冲突报告】以下为数据冲突项，请按【数据冲突高亮规则】处理：\n"
            for c in conflict_items:
                data_conflict_report += (
                    f"- {c['label']}: "
                    f"PDF={c['pdf_value']}{c['pdf_unit']} vs "
                    f"Web={c['web_value']}{c['web_unit']} "
                    f"(差异率: {c['diff_ratio'] * 100:.1f}% 需标记【待人工确认】)\n"
                )
            logger.info(f"   📋 [Writer] 注入 {len(conflict_items)} 条数据冲突报告")

    conflict_context = ""
    if conflict_alerts:
        conflict_context = "\n\n【信源冲突处理规则】\n以下素材中存在信息冲突..."
        for c in conflict_alerts:
            if c.get("status") == "conflict":
                conflict_context += (
                    f"\n- 主题「{c['topic']}」：默认采信内部文档，备注外网不同观点"
                )

    citation_context = (
        "\n\n【引用元数据说明】\n"
        "每条素材前的引用信息包含引用编号、来源类型、置信权重等。\n"
        "在报告正文中使用 [1][2] 格式角标引用，文末参考文献由系统自动生成。\n"
    )

    # pdf_only 模式下追加来源标注约束（使用全局常量）
    pdf_only_constraint = f"\n\n{PDF_ONLY_WRITER_CONSTRAINT}" if pdf_only else ""

    prompt = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"研究课题：{task}\n\n"
                f"【分析大纲】\n{outline_text}\n\n"
                f"【关键论点】\n{json.dumps(arguments, ensure_ascii=False, indent=2)[:2000]}\n\n"
                f"【引用素材】\n\n{material_text}\n"
                f"{data_conflict_report}"
                f"{conflict_context}{citation_context}"
                f"{pdf_only_constraint}"
                f"\n请严格按照大纲结构撰写研报。"
            )
        ),
    ]

    full_content = ""
    try:
        async for chunk in llm.astream(prompt):
            text = extract_text_content(chunk)
            if text:
                full_content += text
                yield f"data: {json.dumps({'step': 'writer_streaming', 'text': text})}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'step': 'error', 'msg': f'Writer 写作失败: {str(e)}'})}\n\n"
        return

    # Step 5: 解析结果
    report = {}
    try:
        if "{" in full_content:
            start = full_content.find("{")
            end = full_content.rfind("}") + 1
            report = json.loads(full_content[start:end])
    except Exception:
        report = {"标题": task, "摘要": "报告生成失败，请重试", "关键发现": []}

    # Step 6: 生成参考文献和冲突预警
    references_section = generate_references_section(citation_metadata, pdf_only=pdf_only)
    conflict_alerts_section = generate_conflict_alerts_section(conflict_alerts)

    result = {
        "report": report,
        "citation_metadata": citation_metadata,
        "conflict_alerts": conflict_alerts,
        "references_section": references_section,
        "report_with_citations": json.dumps(report, ensure_ascii=False),
    }

    yield f"data: {json.dumps({'step': 'writer_done', 'result': result})}\n\n"