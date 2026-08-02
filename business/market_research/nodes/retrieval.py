import re as _re
from collections import Counter as _Counter
from typing import Any, Dict, List

from core.utils.logger import get_logger
from core.config import get_config
from core.search.provider import get_search_provider

from business.market_research.state import AgentState
from business.market_research.utils.material_utils import build_web_query, classify_trust_tier, check_material_sufficiency
from agents.retrieval.reranker import rerank_hybrid_results
from business.market_research.utils.citation_manager import (
    build_citation_metadata,
    detect_conflicts,
)

logger = get_logger(__name__)


def _determine_mode(state: AgentState) -> str:
    """
    确定当前生效的搜索模式。

    规则2：用户输入意图智能识别校验（优先级仅次于用户手动模式）
    规则3：检索模式全局执行路由规则
      1. 仅 PDF（pdf_only）→ 全局禁用联网
      2. PDF + 联网（pdf_web）→ 开启动态子任务路由
      3. 纯联网（web_only）→ 仅允许无 PDF 上传场景

    优先级：
      1. 前端传入的 manual_web_search_mode（用户手动选择优先）
      2. 默认 pdf_web
    """
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    if manual_mode in ("disabled", "pdf_only"):
        return "pdf_only"
    elif manual_mode in ("enabled", "web_only"):
        return "web_only"
    elif manual_mode in ("auto", "pdf_web"):
        return "pdf_web"

    return "pdf_web"


def _execute_pdf_retrieval(search_query: str, pdf_collection: Any, cleaned_chunks: List[Dict]) -> List[Dict]:
    """执行 PDF 混合检索（向量 + BM25）"""
    hybrid_results = []

    if pdf_collection is not None:
        try:
            from core.retrieval.hybrid import HybridRetriever

            hybrid = None
            if isinstance(pdf_collection, dict):
                hybrid = pdf_collection.get("hybrid")

            if hybrid and isinstance(hybrid, HybridRetriever):
                hybrid_results = hybrid.hybrid_search(
                    search_query, n_results=20, vector_weight=0.6, bm25_weight=0.4
                )
        except Exception as e:
            logger.warning(f"   ⚠️ 混合检索失败: {e}")

    if not hybrid_results and pdf_collection is not None:
        try:
            if isinstance(pdf_collection, dict) and pdf_collection.get("type") == "chroma":
                col = pdf_collection.get("collection")
                resp = col.query(
                    query_texts=[search_query],
                    n_results=10,
                    include=["documents", "metadatas"],
                )
                docs = resp.get("documents", []) or []
                if docs and isinstance(docs, list):
                    hybrid_results = [
                        {
                            "text": doc, "score": 1.0, "source_index": i, "source_type": "pdf",
                            "trust_tier": "verified", "source_url": "",
                        }
                        for i, doc in enumerate(docs[0] if isinstance(docs[0], list) else docs)
                    ]
        except Exception as e:
            logger.warning(f"   ⚠️ 回退检索也失败: {e}")

    if not hybrid_results and cleaned_chunks:
        for i, chunk in enumerate(cleaned_chunks):
            text = chunk.get("text", "")
            if search_query[:10] in text:
                hybrid_results.append({
                    "text": text[:800],
                    "score": 0.5,
                    "source_index": i,
                    "source_type": "pdf",
                    "trust_tier": "verified",
                    "source_url": "",
                    "metadata": chunk.get("metadata", {}),
                })

    if not hybrid_results and cleaned_chunks:
        for i, chunk in enumerate(cleaned_chunks[:10]):
            text = chunk.get("text", "")
            if text.strip():
                hybrid_results.append({
                    "text": text[:800],
                    "score": 0.3,
                    "source_index": i,
                    "source_type": "pdf",
                    "trust_tier": "verified",
                    "source_url": "",
                    "metadata": chunk.get("metadata", {}),
                })
        if hybrid_results:
            logger.info(f"   📄 兜底策略: 从 cleaned_chunks 取前 {len(hybrid_results)} 条作为 PDF 检索结果")

    for r in hybrid_results:
        if "vector_score" not in r:
            r["vector_score"] = r.get("score", 0.0) if r.get("source_type") == "vector" else 0.0
        if "bm25_score" not in r:
            r["bm25_score"] = r.get("score", 0.0) if r.get("source_type") == "bm25" else 0.0

    hybrid_results = sorted(hybrid_results, key=lambda x: x.get("score", 0), reverse=True)[:12]

    vec_scores = [r.get("vector_score", 0) for r in hybrid_results[:3]]
    bm25_scores = [r.get("bm25_score", 0) for r in hybrid_results[:3]]
    logger.info(f"   [Retrieval] PDF 检索召回: {len(hybrid_results)} 条")
    logger.info(f"   [Retrieval] 向量相似度 top-3: {[f'{s:.3f}' for s in vec_scores]}")
    logger.info(f"   [Retrieval] BM25 得分 top-3:  {[f'{s:.3f}' for s in bm25_scores]}")

    return hybrid_results


def _execute_web_search(task: str) -> List[Dict]:
    """执行联网搜索（Tavily），多轮搜索"""
    web_results = []
    cfg = get_config()

    if not cfg.web_search_enabled:
        logger.info(f"   🌐 联网搜索未启用，跳过")
        return web_results

    logger.info(f"   🌐 启动联网搜索...")
    for round_num in range(cfg.max_search_rounds):
        query = build_web_query(task, round_num, last_round_success=(len(web_results) > 0 or round_num == 0))
        logger.info(f"   🔎 搜索轮次 {round_num + 1}/{cfg.max_search_rounds}: {query[:40]}...")
        try:
            search_provider = get_search_provider()
            search_response = search_provider.search(query, max_results=5)

            for sidx, item in enumerate(search_response):
                snippet = item.get("content", item.get("snippet", ""))
                url = item.get("url", "")
                trust = classify_trust_tier(url, snippet)
                web_results.append({
                    "text": snippet[:800],
                    "score": 0.7 if trust == "verified" else 0.5,
                    "source_index": sidx,
                    "source_type": "web",
                    "trust_tier": trust,
                    "source_url": url,
                    "source_snippet": snippet[:200],
                    "search_round": round_num + 1,
                })

            logger.info(f"      获得 {len(search_response)} 条, 累积 {len(web_results)} 条")

            if len(web_results) >= 5:
                break

        except Exception as e:
            logger.warning(f"   ⚠️ 联网搜索失败 (轮次 {round_num + 1}): {e}")

    web_results = [r for r in web_results if r.get("trust_tier") != "low_quality"]
    logger.info(f"   🌐 联网搜索最终: {len(web_results)} 条（已过滤低质）")
    return web_results


def retrieval_node(state: AgentState):
    """
    精准检索与降噪节点（SOP 第二阶段）
    根据三大模式 + 意图识别兜底执行不同的检索策略。
    """
    task = state["task"]
    cleaned_chunks = state.get("cleaned_chunks", [])
    pdf_collection = state.get("pdf_collection")
    model_mode = state.get("model_mode", "cloud")
    has_pdf = pdf_collection is not None or bool(cleaned_chunks)

    mode = _determine_mode(state)
    logger.info(f"🔍 [Retrieval] 开始精准检索与降噪... 模式={mode}")
    logger.info(f"   查询: {task[:60]}... 有PDF={has_pdf}")

    # Query 改写：短模糊查询 → 扩写检索词
    search_query = task
    if len(task) < 8 and has_pdf:
        first_texts = "".join([c.get("text", "") for c in cleaned_chunks[:3]])
        words = _re.findall(r'[\u4e00-\u9fff]{2,6}', first_texts[:500])
        word_freq = _Counter(words)
        top_terms = [w for w, c in word_freq.most_common(5) if c >= 2][:3]
        if top_terms:
            search_query = f"{task} {' '.join(top_terms)}"
            logger.info(f"   🔄 Query 改写: '{task}' → '{search_query}'")

    hybrid_results = []
    web_results = []
    web_search_used = False
    total_source = len(cleaned_chunks) if cleaned_chunks else 0

    # 模式 1: pdf_only — 仅 PDF
    if mode == "pdf_only":
        if has_pdf:
            logger.info(f"   📄 [模式:仅PDF] 有PDF → 只检索文档，禁止联网")
            hybrid_results = _execute_pdf_retrieval(search_query, pdf_collection, cleaned_chunks)
            web_search_used = False
        else:
            logger.warning(f"   🚫 [模式:仅PDF] 无PDF → 直接拦截，终止任务")
            return {
                "top_k_chunks": [],
                "source_materials": [],
                "research_results": [],
                "web_search_used": False,
                "material_pool_frozen": True,
                "error_message": "仅 PDF 模式必须上传文件，请上传 PDF 文档后重试",
            }

    # 模式 2: pdf_web — PDF + 联网（强制双渠道）
    elif mode == "pdf_web":
        if has_pdf:
            logger.info(f"   🌐 [模式:PDF+联网] 有PDF → PDF检索 + 强制联网（双渠道合并）")
            hybrid_results = _execute_pdf_retrieval(search_query, pdf_collection, cleaned_chunks)
            web_results = _execute_web_search(task)
            web_search_used = bool(web_results)
        else:
            logger.info(f"   🌐 [模式:PDF+联网] 无PDF → 自动降级纯联网")
            web_results = _execute_web_search(task)
            web_search_used = bool(web_results)

    # 模式 3: web_only — 纯联网
    elif mode == "web_only":
        if has_pdf:
            # 规则1 后端兜底：上传文档列表不为空且 mode=web_only，直接拒绝执行任务
            logger.warning(f"   🚫 [规则1 后端兜底] 有PDF + 纯联网模式 → 拒绝执行")
            return {
                "top_k_chunks": [],
                "source_materials": [],
                "research_results": [],
                "web_search_used": False,
                "material_pool_frozen": True,
                "error_message": "⚠️ 提示：您已上传PDF文档，纯联网模式不会读取本地文档内容。如需使用文档，请选择【仅PDF】或【PDF+联网】模式；若仅需全网信息，请先清空所有PDF。",
                "web_only_with_pdf_notice": "⚠️ 提示：您已上传PDF文档，纯联网模式不会读取本地文档内容。如需使用文档，请选择【仅PDF】或【PDF+联网】模式；若仅需全网信息，请先清空所有PDF。",
            }
        else:
            logger.info(f"   🌐 [模式:纯联网] 无PDF，只执行联网")
        web_results = _execute_web_search(task)
        web_search_used = bool(web_results)

    # 信息充足性判定（仅打印日志，不控制分支）
    sufficiency = check_material_sufficiency(hybrid_results + web_results, task, total_source)
    logger.info(f"   📋 信息充足性评估（仅参考）: {sufficiency}")

    # 合并 PDF + 网页素材
    all_candidates = hybrid_results + web_results
    logger.info(f"   📦 合并候选池: {len(all_candidates)} 条 (PDF: {len(hybrid_results)}, 网页: {len(web_results)})")

    # Rerank 重排序
    if web_results:
        if all_candidates:
            reranked = rerank_hybrid_results(
                query=task,
                hybrid_results=all_candidates,
                model_mode=model_mode,
                top_k=8,
            )
            logger.info(f"   [Retrieval] Rerank 过滤: 输入 {len(all_candidates)} 条, 输出 Top-{len(reranked)} 条")
        if reranked:
            top_score = reranked[0].get("rerank_score", 0)
            bottom_score = reranked[-1].get("rerank_score", 0)
            logger.info(f"   [Retrieval] Rerank 最高分: {top_score:.2f}, 最低分: {bottom_score:.2f}")
        else:
            reranked = []
            logger.warning("   ⚠️ 无任何检索结果")
    else:
        reranked = sorted(all_candidates, key=lambda x: x.get("score", 0), reverse=True)[:8]
        for rank, item in enumerate(reranked):
            item["rerank_score"] = item.get("score", 0.5)
            item["relevance_label"] = "相关"
            item["rerank_rank"] = rank + 1
        logger.info(f"   [Retrieval] 纯 PDF 模式，跳过 LLM 重排，按分数排序取 Top-{len(reranked)}")

    if len(reranked) > 12:
        reranked = reranked[:12]
        logger.info(f"   📊 相对排序优先: 截取 Top-12（保留 {len(reranked)} 条）")

    # 构建素材列表 + 素材池冻结
    source_materials = []
    for i, item in enumerate(reranked):
        source_materials.append({
            "text": item.get("text", ""),
            "source_index": item.get("source_index", i),
            "rerank_score": item.get("rerank_score", 0),
            "source_type": item.get("source_type", "unknown"),
            "trust_tier": item.get("trust_tier", "unverified"),
            "source_url": item.get("source_url", ""),
            "source_snippet": item.get("source_snippet", ""),
            "metadata": item.get("metadata", {}),
        })

    # ============================================================
    #  【信源溯源改造】生成引用元数据
    # ============================================================
    # pdf_only 模式下传递模式标记给 citation_manager
    pdf_only = mode == "pdf_only"
    citation_metadata = build_citation_metadata(source_materials, pdf_only=pdf_only)
    logger.info(f"   [Retrieval] 生成 {len(citation_metadata)} 条引用元数据")

    # 初步检测冲突（仅当同时有 PDF 和 Web 来源时）
    conflict_alerts = []
    if hybrid_results and web_results:
        conflict_alerts = detect_conflicts(hybrid_results, web_results, citation_metadata, pdf_only=pdf_only)
        if conflict_alerts:
            conflict_count = len([c for c in conflict_alerts if c.get("status") == "conflict"])
            logger.warning(f"   [Retrieval] 检测到 {conflict_count} 处信息冲突")

    return {
        "top_k_chunks": reranked,
        "source_materials": source_materials,
        "research_results": [item.get("text", "") for item in reranked],
        "web_search_used": web_search_used,
        "material_pool_frozen": True,
        "citation_metadata": citation_metadata,
        "conflict_alerts": conflict_alerts,
    }
