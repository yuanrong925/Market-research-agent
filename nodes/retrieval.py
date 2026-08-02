"""
第二阶段：精准检索与降噪节点（Retrieval）

SOP 规范（2026-07 更新 — 三大基础模式 + 意图识别兜底）：
  1. PDF 混合检索：向量检索 + BM25 关键词检索，仅在有 PDF 时执行
  2. 三大模式执行规则：
     a. pdf_only（仅PDF）：有PDF只检索文档，禁止联网；无PDF直接拦截
     b. pdf_web（PDF+联网）：有PDF则PDF检索+强制联网（双渠道）；无PDF降级纯联网
     c. web_only（纯联网）：无论有无PDF，只执行联网，完全忽略文档
  3. 意图识别兜底（最高优先级）：检测到总结/解读类意图时，强制锁定仅PDF模式
  4. 彻底删除「素材充足就跳过联网」的智能判断
     - pdf_web模式下联网搜索是硬性步骤，不受PDF召回数量、分数影响
     - 充足度判断仅保留打印日志、辅助LLM参考，不再控制检索分支开关
  5. 网页结果信任度分级
  6. 合并 PDF + 网页素材 → 轻量 Rerank 去重排序
  7. 素材池冻结
"""

from typing import Any, Dict, List

from agents.config import (
    WEB_SEARCH_ENABLED,
    MAX_SEARCH_ROUNDS,
    search_tool,
)
from agents.retrieval.rag import (
    query_pdf_collection,
    hybrid_search_collection,
)
from agents.retrieval.reranker import rerank_hybrid_results
from agents.state import AgentState
from tools.logger import get_logger

logger = get_logger(__name__)
from tools.material_utils import (
    classify_trust_tier,
    check_material_sufficiency,
    build_web_query,
)


def _determine_mode(state: AgentState) -> str:
    """
    确定当前生效的搜索模式。
    优先级（从高到低）：
      1. 意图识别兜底（intent_override_triggered == True → 强制 only PDF）
      2. 前端传入的 manual_web_search_mode
      3. 默认 pdf_web
    """
    # 第一层优先级：意图识别兜底
    if state.get("intent_override_triggered", False):
        target = state.get("intent_override_target_mode", "disabled")
        logger.info(f"   🏆 [模式决策] 意图识别兜底生效: 强制锁定为仅PDF模式 (target={target})")
        return "pdf_only"

    # 第二层优先级：前端传入的 search_mode
    manual_mode = state.get("manual_web_search_mode", "auto")
    if manual_mode == "disabled":
        return "pdf_only"
    elif manual_mode == "enabled":
        return "web_only"
    elif manual_mode == "auto":
        return "pdf_web"

    # 默认
    return "pdf_web"


def _execute_pdf_retrieval(search_query: str, pdf_collection: Any, cleaned_chunks: List[Dict]) -> List[Dict]:
    """
    执行 PDF 混合检索（向量 + BM25）。
    如果 pdf_collection 存在则优先使用，否则降级到 cleaned_chunks。
    """
    hybrid_results = []

    if pdf_collection is not None:
        try:
            hybrid_results = hybrid_search_collection(
                pdf_collection,
                query=search_query,
                n_results=20,
                vector_weight=0.6,
                bm25_weight=0.4,
            )
        except Exception as e:
            logger.warning(f"   ⚠️ 混合检索失败: {e}")

    if not hybrid_results and pdf_collection is not None:
        try:
            pdf_texts = query_pdf_collection(pdf_collection, search_query, n_results=10)
            hybrid_results = [
                {
                    "text": t, "score": 1.0, "source_index": i, "source_type": "pdf",
                    "trust_tier": "verified", "source_url": "",
                }
                for i, t in enumerate(pdf_texts)
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

    # 兜底：取前 N 个块
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

    # 补充两套独立分数
    for r in hybrid_results:
        if "vector_score" not in r:
            r["vector_score"] = r.get("score", 0.0) if r.get("source_type") == "vector" else 0.0
        if "bm25_score" not in r:
            r["bm25_score"] = r.get("score", 0.0) if r.get("source_type") == "bm25" else 0.0

    # 按融合分降序排列，取 Top-N
    hybrid_results = sorted(hybrid_results, key=lambda x: x.get("score", 0), reverse=True)[:12]

    # 日志
    vec_scores = [r.get("vector_score", 0) for r in hybrid_results[:3]]
    bm25_scores = [r.get("bm25_score", 0) for r in hybrid_results[:3]]
    logger.info(f"   [Retrieval] PDF 检索召回: {len(hybrid_results)} 条")
    logger.info(f"   [Retrieval] 向量相似度 top-3: {[f'{s:.3f}' for s in vec_scores]}")
    logger.info(f"   [Retrieval] BM25 得分 top-3:  {[f'{s:.3f}' for s in bm25_scores]}")

    return hybrid_results


def _execute_web_search(task: str) -> List[Dict]:
    """
    执行联网搜索（Tavily），多轮搜索。
    返回已过滤低质内容的搜索结果列表。
    """
    web_results = []

    if not WEB_SEARCH_ENABLED or search_tool is None:
        logger.info(f"   🌐 联网搜索未启用或工具不可用，跳过")
        return web_results

    logger.info(f"   🌐 启动联网搜索...")
    for round_num in range(MAX_SEARCH_ROUNDS):
        query = build_web_query(task, round_num, last_round_success=(len(web_results) > 0 or round_num == 0))
        logger.info(f"   🔎 搜索轮次 {round_num + 1}/{MAX_SEARCH_ROUNDS}: {query[:40]}...")
        try:
            search_response = search_tool.invoke(query)
            if isinstance(search_response, dict):
                search_items = search_response.get("results", [])
            elif isinstance(search_response, list):
                search_items = search_response
            else:
                search_items = [{"content": str(search_response), "url": ""}]

            for sidx, item in enumerate(search_items):
                if isinstance(item, dict):
                    snippet = item.get("content", item.get("snippet", ""))
                    url = item.get("url", "")
                else:
                    snippet = str(item)
                    url = ""
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

            logger.info(f"      获得 {len(search_items)} 条, 累积 {len(web_results)} 条")

            if len(web_results) >= 5:
                break

        except Exception as e:
            logger.warning(f"   ⚠️ 联网搜索失败 (轮次 {round_num + 1}): {e}")

    # 过滤低质内容
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

    # 确定当前模式
    mode = _determine_mode(state)
    logger.info(f"🔍 [Retrieval] 开始精准检索与降噪... 模式={mode}")
    logger.info(f"   查询: {task[:60]}... 有PDF={has_pdf}")

    # ===== Query 改写：短模糊查询 → 扩写检索词 =====
    search_query = task
    if len(task) < 8 and has_pdf:
        first_texts = "".join([c.get("text", "") for c in cleaned_chunks[:3]])
        import re as _re
        words = _re.findall(r'[\u4e00-\u9fff]{2,6}', first_texts[:500])
        from collections import Counter as _Counter
        word_freq = _Counter(words)
        top_terms = [w for w, c in word_freq.most_common(5) if c >= 2][:3]
        if top_terms:
            search_query = f"{task} {' '.join(top_terms)}"
            logger.info(f"   🔄 Query 改写: '{task}' → '{search_query}'")

    # ===== 初始化变量 =====
    hybrid_results = []
    web_results = []
    web_search_used = False
    total_source = len(cleaned_chunks) if cleaned_chunks else 0
    is_small_doc = total_source <= 10

    # ==========================================
    #  模式 1: pdf_only — 仅 PDF
    # ==========================================
    if mode == "pdf_only":
        if has_pdf:
            logger.info(f"   📄 [模式:仅PDF] 有PDF → 只检索文档，禁止联网")
            hybrid_results = _execute_pdf_retrieval(search_query, pdf_collection, cleaned_chunks)
            web_search_used = False
        else:
            # 无PDF → 直接拦截
            logger.warning(f"   🚫 [模式:仅PDF] 无PDF → 直接拦截，终止任务")
            return {
                "top_k_chunks": [],
                "source_materials": [],
                "research_results": [],
                "web_search_used": False,
                "material_pool_frozen": True,
                "error_message": "仅 PDF 模式必须上传文件，请上传 PDF 文档后重试",
            }

    # ==========================================
    #  模式 2: pdf_web — PDF + 联网（强制双渠道）
    # ==========================================
    elif mode == "pdf_web":
        if has_pdf:
            logger.info(f"   🌐 [模式:PDF+联网] 有PDF → PDF检索 + 强制联网（双渠道合并）")
            hybrid_results = _execute_pdf_retrieval(search_query, pdf_collection, cleaned_chunks)
            # 强制联网搜索（硬性步骤，不受PDF检索结果影响）
            web_results = _execute_web_search(task)
            web_search_used = bool(web_results)
        else:
            # 无PDF → 自动降级纯联网
            logger.info(f"   🌐 [模式:PDF+联网] 无PDF → 自动降级纯联网")
            web_results = _execute_web_search(task)
            web_search_used = bool(web_results)

    # ==========================================
    #  模式 3: web_only — 纯联网
    # ==========================================
    elif mode == "web_only":
        if has_pdf:
            logger.info(f"   🌐 [模式:纯联网] 有PDF → 忽略文档，只执行联网")
            # 通知后续节点：用户选择了纯联网模式，已上传的PDF被忽略
            state["web_only_with_pdf_notice"] = "您上传了PDF文件，但当前模式为「纯联网搜索」，已忽略PDF文档，仅使用网络搜索结果。如需要基于PDF生成报告，请切换至「仅PDF」或「PDF+联网」模式。"
        else:
            logger.info(f"   🌐 [模式:纯联网] 无PDF，只执行联网")
        web_results = _execute_web_search(task)
        web_search_used = bool(web_results)

    # ===== 信息充足性判定（仅打印日志，不控制分支） =====
    sufficiency = check_material_sufficiency(hybrid_results + web_results, task, total_source)
    logger.info(f"   📋 信息充足性评估（仅参考）: {sufficiency}")

    # ===== 合并 PDF + 网页素材 =====
    all_candidates = hybrid_results + web_results
    logger.info(f"   📦 合并候选池: {len(all_candidates)} 条 (PDF: {len(hybrid_results)}, 网页: {len(web_results)})")

    # ===== Rerank 重排序 =====
    if web_results:
        # 有网页结果时，用 LLM 重排来混合排序
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
        # 纯 PDF 模式：跳过 LLM 重排，直接按分数排序取 top-K
        reranked = sorted(all_candidates, key=lambda x: x.get("score", 0), reverse=True)[:8]
        for rank, item in enumerate(reranked):
            item["rerank_score"] = item.get("score", 0.5)
            item["relevance_label"] = "相关"
            item["rerank_rank"] = rank + 1
        logger.info(f"   [Retrieval] 纯 PDF 模式，跳过 LLM 重排，按分数排序取 Top-{len(reranked)}")

    # ===== 相对排序优先 =====
    if len(reranked) > 12:
        reranked = reranked[:12]
        logger.info(f"   📊 相对排序优先: 截取 Top-12（保留 {len(reranked)} 条）")

    # ---- Step 5: 构建素材列表 + 素材池冻结 ----
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

    return {
        "top_k_chunks": reranked,
        "source_materials": source_materials,
        "research_results": [item.get("text", "") for item in reranked],
        "web_search_used": web_search_used,
        "material_pool_frozen": True,
    }
