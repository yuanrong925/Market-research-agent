from typing import Any, Dict, List

from core.utils.logger import get_logger
from core.config import get_config
from core.search.provider import get_search_provider

from business.market_research.state import AgentState
from business.market_research.utils.material_utils import build_web_query, classify_trust_tier, check_material_sufficiency
from business.market_research.utils.web_cleaner import clean_webpages_batch
from agents.retrieval.reranker import rerank_hybrid_results
from business.market_research.utils.citation_manager import (
    build_citation_metadata,
    detect_conflicts,
)
from business.market_research.utils.constants import (
    RETRIEVAL_IRRELEVANT_THRESHOLD,
    RETRIEVAL_INSUFFICIENT_THRESHOLD,
    RETRIEVAL_RELEVANT_THRESHOLD,
    LOCAL_RETRIEVAL_IRRELEVANT_THRESHOLD,
    LOCAL_RETRIEVAL_INSUFFICIENT_THRESHOLD,
    LOCAL_RETRIEVAL_RELEVANT_THRESHOLD,
    MAX_WEB_PAGES_TO_CLEAN,
)

logger = get_logger(__name__)


def _determine_mode(state: AgentState) -> str:
    """
    确定当前生效的搜索模式。

    规则3：检索模式全局执行路由规则
      1. 仅 PDF（pdf_only）→ 全局禁用联网，仅检索 PDF
      2. PDF + 联网（pdf_web）→ 同时检索 PDF 和联网搜索；无 PDF 时降级为纯联网
      3. 纯联网（web_only）→ 完全忽略上传的 PDF，仅执行联网搜索（场景5/10）

    优先级：
      1. 前端传入的 manual_web_search_mode（用户手动选择优先）
      2. 默认 pdf_web
    """
    manual_mode = state.get("manual_web_search_mode", "auto").lower().replace("-", "_")
    if manual_mode in ("disabled", "pdf_only"):
        return "pdf_only"
    elif manual_mode in ("enabled", "web_only"):
        return "web_only"
    elif manual_mode in ("auto", "pdf_web"):
        return "pdf_web"

    logger.warning(f"   ⚠️ 无法识别的 manual_web_search_mode: '{manual_mode}'，默认使用 pdf_web")
    return "pdf_web"


def _execute_pdf_retrieval(search_query: str, pdf_collection: Any, cleaned_chunks: List[Dict]) -> List[Dict]:
    """执行 PDF 混合检索（向量 + BM25）

    修复：
      1. 移除「取前 N 个无关 chunk 作为保底」的兜底逻辑，避免幻觉
      2. 降级到 inmemory 时明确记录日志，上游可据此判断是否仅 BM25
      3. Chroma 回退查询时使用实际距离计算相似度，而非硬编码 1.0
    """
    hybrid_results = []

    # 检查是否降级到 inmemory
    is_fallback = False
    fallback_reason = ""
    if isinstance(pdf_collection, dict):
        is_fallback = pdf_collection.get("fallback", False)
        fallback_reason = pdf_collection.get("fallback_reason", "")

    if is_fallback:
        logger.info(f"   [Retrieval] PDF 集合处于降级模式 (inmemory): {fallback_reason}")
        logger.info(f"   [Retrieval] 仅 BM25 关键词检索可用，无语义向量检索")

    # 兼容处理：pdf_collection 可能是 dict、str（旧版）、None
    pdf_dict = None
    if isinstance(pdf_collection, dict):
        pdf_dict = pdf_collection
    elif pdf_collection is not None:
        # 旧版状态：pdf_collection 是字符串或其他类型，跳过
        logger.warning(f"   ⚠️ pdf_collection 类型异常 ({type(pdf_collection).__name__})，跳过混合检索，尝试精确匹配")

    if pdf_dict is not None:
        try:
            from core.retrieval.hybrid import HybridRetriever

            hybrid = pdf_dict.get("hybrid")

            if hybrid and isinstance(hybrid, HybridRetriever):
                hybrid_results = hybrid.hybrid_search(
                    search_query, n_results=20, vector_weight=0.6, bm25_weight=0.4
                )
        except Exception as e:
            logger.warning(f"   ⚠️ 混合检索失败: {e}")

    # 混合检索无结果但 Chroma 集合存在时，回退到纯向量检索
    # 修复：使用实际距离计算相似度，而非硬编码 1.0
    if not hybrid_results and pdf_dict is not None:
        try:
            if pdf_dict.get("type") in ("chroma",):
                col = pdf_dict.get("collection")
                if col is not None:
                    resp = col.query(
                        query_texts=[search_query],
                        n_results=10,
                        include=["documents", "metadatas", "distances"],
                    )
                    docs = resp.get("documents", []) or []
                    dists = resp.get("distances", []) or []
                    if docs and isinstance(docs, list):
                        for i, doc in enumerate(docs[0] if isinstance(docs[0], list) else docs):
                            dist = 0.0
                            if dists and isinstance(dists[0], list) and i < len(dists[0]):
                                dist = dists[0][i]
                            similarity = 1.0 / (1.0 + dist) if dist >= 0 else 0.0
                            hybrid_results.append({
                                "text": doc, "score": similarity, "source_index": i, "source_type": "pdf",
                                "trust_tier": "verified", "source_url": "",
                            })
        except Exception as e:
            logger.warning(f"   ⚠️ 回退向量检索也失败: {e}")

    # 精确匹配兜底（仅在混合检索和向量检索都无结果时）
    # 修复：移除「取前 N 个无关 chunk 作为保底」的逻辑，避免强行塞入不相关内容产生幻觉
    # 仅当查询关键词前 10 字符在 chunk 内容中出现时才匹配
    # 修复2: 精确匹配 score 从 0.5 提升到 0.75+，因为关键词出现在内容中是强相关信号
    if not hybrid_results and cleaned_chunks:
        query_prefix = search_query[:10].strip().lower()
        if query_prefix:
            match_count = 0
            for i, chunk in enumerate(cleaned_chunks):
                text = chunk.get("text", "")
                if query_prefix in text.lower():
                    # 计算匹配密度：关键词在文本中出现次数占比，作为分数加成
                    keyword_count = text.lower().count(query_prefix)
                    density_bonus = min(keyword_count / 10, 0.15)  # 最多加 0.15
                    score = min(0.75 + density_bonus, 0.95)  # 上限 0.95
                    match_count += 1
                    hybrid_results.append({
                        "text": text[:800],
                        "score": score,
                        "source_index": i,
                        "source_type": "pdf",
                        "trust_tier": "verified",
                        "source_url": "",
                        "metadata": chunk.get("metadata", {}),
                    })
            if hybrid_results:
                logger.info(f"   📄 精确匹配兜底: 从 cleaned_chunks 中找到 {len(hybrid_results)} 条包含查询关键词的片段 (命中率={match_count}/{len(cleaned_chunks)})")
            else:
                logger.info(f"   📄 精确匹配兜底: cleaned_chunks 中未找到包含查询关键词的片段，返回空")
        else:
            logger.info(f"   📄 精确匹配兜底: 查询关键词过短，跳过")

    # 补全分数字段：所有结果类型都使用 score 作为默认值
    # hybrid_search 已经返回 vector_score 和 bm25_score（可能为 0.0）
    for r in hybrid_results:
        if "vector_score" not in r:
            r["vector_score"] = r.get("score", 0.0)
        if "bm25_score" not in r:
            r["bm25_score"] = r.get("score", 0.0)

    hybrid_results = sorted(hybrid_results, key=lambda x: x.get("score", 0), reverse=True)[:12]

    vec_scores = [r.get("vector_score", 0) for r in hybrid_results[:3]]
    bm25_scores = [r.get("bm25_score", 0) for r in hybrid_results[:3]]
    logger.info(f"   [Retrieval] PDF 检索召回: {len(hybrid_results)} 条 (降级={is_fallback})")
    if vec_scores and any(v > 0 for v in vec_scores):
        logger.info(f"   [Retrieval] 向量相似度 top-3: {[f'{s:.3f}' for s in vec_scores]}")
    else:
        logger.info(f"   [Retrieval] 向量检索不可用（降级模式），仅 BM25 关键词检索")
    if bm25_scores and any(b > 0 for b in bm25_scores):
        logger.info(f"   [Retrieval] BM25 得分 top-3:  {[f'{s:.3f}' for s in bm25_scores]}")
    else:
        logger.info(f"   [Retrieval] BM25 关键词检索无命中")

    return hybrid_results


def _execute_web_search(task: str) -> List[Dict]:
    """执行联网搜索（Tavily）+ 网页清洗，多轮搜索

    ✅ 新增网页清洗的唯一窗口期：
      1. 搜索获得原始网页 URL 列表
      2. 逐个抓取网页原始 HTML
      3. 清洗：过滤广告/导航/页脚/重复
      4. 保留正文原文切片，不交由 LLM 概括改写
      5. 清洗失败时降级使用 snippet
    """
    web_results = []
    cfg = get_config()

    if not cfg.web_search_enabled:
        logger.info(f"   🌐 联网搜索未启用，跳过")
        return web_results

    logger.info(f"   🌐 启动联网搜索...")

    # ----- 阶段 1: 搜索 -----
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
                    "cleaned_chunks": [],  # 占位，下文清洗后填充
                    "fetch_status": "pending",
                })

            logger.info(f"      获得 {len(search_response)} 条, 累积 {len(web_results)} 条")

            if len(web_results) >= 5:
                break

        except Exception as e:
            logger.warning(f"   ⚠️ 联网搜索失败 (轮次 {round_num + 1}): {e}")

    web_results = [r for r in web_results if r.get("trust_tier") != "low_quality"]

    # ----- 阶段 2: 网页清洗（唯一联网窗口期）-----
    logger.info(f"   🌐 [WebCleaner] 开始清洗 {len(web_results)} 个网页...")
    max_pages = getattr(cfg, "max_web_pages_to_clean", MAX_WEB_PAGES_TO_CLEAN)
    all_cleaned = clean_webpages_batch(web_results, max_pages=max_pages)

    # 将清洗后的切片贴回对应的 web_results 条目
    for result in web_results:
        url = result.get("source_url", "")
        matching = [c for c in all_cleaned if c.get("source_url", "") == url]
        if matching:
            result["cleaned_chunks"] = matching
            result["fetch_status"] = matching[0].get("fetch_status", "cleaned")
            # 用清洗后的完整正文替换 snippet
            full_text = "\n\n".join([c["text"] for c in matching])
            if full_text and len(full_text) > len(result.get("text", "")):
                result["text"] = full_text[:8000]  # 保留更长正文
                result["cleaned_full_text"] = full_text
        else:
            result["fetch_status"] = "fallback"

    cleaned_count = sum(1 for r in web_results if r.get("fetch_status") in ("full_html", "cleaned"))
    fallback_count = sum(1 for r in web_results if r.get("fetch_status") == "fallback")
    total_chunks = sum(len(r.get("cleaned_chunks", [])) for r in web_results)
    logger.info(f"   🌐 网页清洗完成: {cleaned_count} 个成功清洗, {fallback_count} 个降级, 共 {total_chunks} 个切片")

    return web_results


def _classify_sub_task_relevance(
    reranked: List[Dict[str, Any]],
    mode: str,
    sub_task: str,
    route_tag: str,
    model_mode: str = "cloud",
) -> dict:
    """
    对单条子任务的检索结果进行相关性判定。
    返回子任务粒度的相关性判定结果。

    根据 model_mode 动态选择阈值：
      - cloud: 使用云端标准阈值（更高标准）
      - local: 使用本地模型宽松阈值（避免误阻断）
    """
    if not reranked:
        return {
            "sub_task": sub_task,
            "route_tag": route_tag,
            "retrieved_chunks": [],
            "relevance": "irrelevant",
            "relevance_score": 0.0,
            "reason": "无任何检索结果返回，无法找到相关信息",
        }

    max_score = max(r.get("rerank_score", 0) for r in reranked)
    min_score = min(r.get("rerank_score", 0) for r in reranked)
    avg_score = sum(r.get("rerank_score", 0) for r in reranked) / len(reranked)

    logger.info(f"   [子任务相关性] '{sub_task[:30]}...' 评分范围: {min_score:.2f}~{max_score:.2f} (avg={avg_score:.2f}) mode={model_mode}")

    # 根据 model_mode 动态选择阈值
    if model_mode == "local":
        irrelevant_threshold = LOCAL_RETRIEVAL_IRRELEVANT_THRESHOLD
        insufficient_threshold = LOCAL_RETRIEVAL_INSUFFICIENT_THRESHOLD
    else:
        irrelevant_threshold = RETRIEVAL_IRRELEVANT_THRESHOLD
        insufficient_threshold = RETRIEVAL_INSUFFICIENT_THRESHOLD

    if max_score < irrelevant_threshold:
        return {
            "sub_task": sub_task,
            "route_tag": route_tag,
            "retrieved_chunks": reranked,
            "relevance": "irrelevant",
            "relevance_score": max_score,
            "reason": f"全部检索结果与子任务不相关 (max_score={max_score:.2f} < {irrelevant_threshold})",
        }
    elif max_score < insufficient_threshold:
        return {
            "sub_task": sub_task,
            "route_tag": route_tag,
            "retrieved_chunks": reranked,
            "relevance": "insufficient",
            "relevance_score": max_score,
            "reason": f"检索结果相关性不足 (max_score={max_score:.2f} < {insufficient_threshold})，素材不足以支撑完整分析",
        }
    else:
        return {
            "sub_task": sub_task,
            "route_tag": route_tag,
            "retrieved_chunks": reranked,
            "relevance": "relevant",
            "relevance_score": max_score,
            "reason": f"检索结果与子任务相关 (max_score={max_score:.2f} >= {insufficient_threshold})",
        }


def _retrieve_for_sub_task(
    sub_task_text: str,
    route_tag: str,
    state: AgentState,
    pdf_collection: Any,
    cleaned_chunks: List[Dict],
    pre_fetched_web_results: List[Dict] = None,
) -> dict:
    """
    对单条子任务执行检索、rerank、相关性判定。
    返回子任务粒度的完整检索结果。

    参数:
      pre_fetched_web_results: 在遍历子任务前已一次性批量搜索的结果。
                               如果传入，则不再独立调用 _execute_web_search。
    """
    model_mode = state.get("model_mode", "cloud")
    mode = _determine_mode(state)
    has_pdf = pdf_collection is not None or bool(cleaned_chunks)

    # 判断 route_tag 与全局模式是否冲突
    if route_tag == "web_only" and mode == "pdf_only":
        logger.warning(f"   ⚠️ [子任务] '{sub_task_text[:30]}...' 标记为 web_only 但全局模式为 pdf_only")
        return {
            "sub_task": sub_task_text,
            "route_tag": route_tag,
            "retrieved_chunks": [],
            "relevance": "insufficient",
            "relevance_score": 0.0,
            "reason": "子任务需要联网搜索，但当前全局模式为仅PDF，无法获取外部信息",
        }

    if route_tag == "pdf_only" and mode == "web_only":
        logger.warning(f"   ⚠️ [子任务] '{sub_task_text[:30]}...' 标记为 pdf_only 但全局模式为 web_only")
        return {
            "sub_task": sub_task_text,
            "route_tag": route_tag,
            "retrieved_chunks": [],
            "relevance": "insufficient",
            "relevance_score": 0.0,
            "reason": "子任务需要PDF检索，但当前全局模式为纯联网，无法读取文档内容",
        }

    # 执行检索
    hybrid_results = []
    web_results = []

    # 根据 route_tag 和模式决定是否执行PDF检索
    if mode in ("pdf_only", "pdf_web") and has_pdf:
        if route_tag in ("pdf_only", "pdf_web"):
            logger.info(f"   📄 [子任务] PDF检索: '{sub_task_text[:30]}...'")
            hybrid_results = _execute_pdf_retrieval(sub_task_text, pdf_collection, cleaned_chunks)

    # 根据 route_tag 和模式决定是否执行联网搜索
    if mode in ("web_only", "pdf_web"):
        if route_tag in ("web_only", "pdf_web"):
            if pre_fetched_web_results:
                # 使用预搜索的批量结果，不再独立联网
                web_results = pre_fetched_web_results
                logger.info(f"   🌐 [子任务] 使用预搜索批量结果: {len(web_results)} 条")
            else:
                logger.info(f"   🌐 [子任务] 联网搜索: '{sub_task_text[:30]}...'")
                web_results = _execute_web_search(sub_task_text)

    all_candidates = hybrid_results + web_results

    if not all_candidates:
        return {
            "sub_task": sub_task_text,
            "route_tag": route_tag,
            "retrieved_chunks": [],
            "relevance": "irrelevant",
            "relevance_score": 0.0,
            "reason": "检索未返回任何结果",
        }

    # Rerank 重排序
    if web_results:
        reranked = rerank_hybrid_results(
            query=sub_task_text,
            hybrid_results=all_candidates,
            model_mode=model_mode,
            top_k=6,
        )
    else:
        reranked = sorted(all_candidates, key=lambda x: x.get("score", 0), reverse=True)[:6]
        for rank, item in enumerate(reranked):
            item["rerank_score"] = item.get("score", 0.0)  # 保留原始分数，不硬编码 0.5
            item["relevance_label"] = "相关"
            item["rerank_rank"] = rank + 1

    # 相关性判定
    result = _classify_sub_task_relevance(reranked, mode, sub_task_text, route_tag, model_mode)
    result["retrieved_chunks"] = reranked
    return result




def retrieval_node(state: AgentState):
    """
    精准检索与降噪节点（SOP 第二阶段）
    按子任务逐个检索，聚合结果。
    """
    task = state["task"]
    sub_tasks = state.get("sub_tasks", [])
    cleaned_chunks = state.get("cleaned_chunks", [])
    pdf_collection = state.get("pdf_collection")
    model_mode = state.get("model_mode", "cloud")
    has_pdf = pdf_collection is not None or bool(cleaned_chunks)

    mode = _determine_mode(state)
    logger.info(f"🔍 [Retrieval] start... mode={mode}")

    # no sub_tasks -> fallback to whole task
    if not sub_tasks:
        logger.info("no sub_tasks, fallback")
        search_query = task
        hybrid_results = []
        web_results = []
        web_search_used = False
        total_source = len(cleaned_chunks) if cleaned_chunks else 0

        if mode == "pdf_only":
            if has_pdf:
                hybrid_results = _execute_pdf_retrieval(search_query, pdf_collection, cleaned_chunks)
                web_search_used = False
                if not hybrid_results:
                    # 场景2/9: 文档内无相关数据，友好提示
                    return {"top_k_chunks": [],"source_materials": [],"research_results": [],"web_search_used": False,"material_pool_frozen": True,"terminate_reason": "NO_CONTENT_IN_PDF","error_message": "📄 该文档未包含您所查询的数据。请尝试：1）上传包含相关数据的文档 2）切换至「PDF+联网」或「纯联网」模式以获取更多信息","early_terminate": True,"info_limitation_note": "文档未包含该数据，请切换至联网模式或上传包含相关数据的文档"}
            else:
                # 场景7: 未上传PDF却选择仅PDF模式
                return {"top_k_chunks": [],"source_materials": [],"research_results": [],"web_search_used": False,"material_pool_frozen": True,"error_message": "📄 您选择了【仅PDF】模式，但未上传PDF文件。请上传PDF文档，或切换至「纯联网」模式","early_terminate": True}
        elif mode == "pdf_web":
            if has_pdf:
                hybrid_results = _execute_pdf_retrieval(search_query, pdf_collection, cleaned_chunks)
                web_results = _execute_web_search(task)
                web_search_used = bool(web_results)
            else:
                # 场景8: 无PDF时优雅降级为纯联网搜索，不终止
                logger.info(f"   [Retrieval] PDF+联网模式但无PDF文件，自动降级为纯联网搜索")
                web_results = _execute_web_search(task)
                web_search_used = bool(web_results)
        elif mode == "web_only":
            # 场景5/10: 纯联网模式下，完全忽略上传的PDF，只依靠网络搜索
            if has_pdf:
                logger.info(f"   [Retrieval] 纯联网模式，忽略上传的PDF，只执行联网搜索")
            web_results = _execute_web_search(task)
            web_search_used = bool(web_results)

        all_candidates = hybrid_results + web_results

        if web_results:
            if all_candidates:
                reranked = rerank_hybrid_results(query=task, hybrid_results=all_candidates, model_mode=model_mode, top_k=8)
            else:
                reranked = []
        else:
            reranked = sorted(all_candidates, key=lambda x: x.get("score", 0), reverse=True)[:8]
            for rank, item in enumerate(reranked):
                item["rerank_score"] = item.get("score", 0.0)  # 保留原始分数，不硬编码 0.5
                item["relevance_label"] = "相关"
                item["rerank_rank"] = rank + 1

        if len(reranked) > 12:
            reranked = reranked[:12]

        retrieval_relevance = "relevant"
        if reranked:
            max_score = max(r.get("rerank_score", 0) for r in reranked)
            # 根据 model_mode 动态选择阈值
            if model_mode == "local":
                irrelevant_threshold = LOCAL_RETRIEVAL_IRRELEVANT_THRESHOLD
                insufficient_threshold = LOCAL_RETRIEVAL_INSUFFICIENT_THRESHOLD
            else:
                irrelevant_threshold = RETRIEVAL_IRRELEVANT_THRESHOLD
                insufficient_threshold = RETRIEVAL_INSUFFICIENT_THRESHOLD
            if max_score < irrelevant_threshold:
                retrieval_relevance = "irrelevant"
                if mode == "pdf_only":
                    # 场景2/9: PDF内容完全不相关→早停
                    return {"top_k_chunks": [],"source_materials": [],"research_results": [],"web_search_used": False,"material_pool_frozen": True,"terminate_reason": "ALL_SUB_TASKS_IRRELEVANT","retrieval_relevance": "irrelevant","early_terminate": True,"error_message": "📄 该文档内容与您的查询不相关。请尝试切换至联网模式或上传更相关的文档","info_limitation_note": "文档内容不相关"}
            elif max_score < insufficient_threshold:
                retrieval_relevance = "insufficient"

        state["retrieval_relevance"] = retrieval_relevance

        source_materials = []
        for i, item in enumerate(reranked):
            source_materials.append({
                "text": item.get("text", ""), "source_index": item.get("source_index", i),
                "rerank_score": item.get("rerank_score", 0), "source_type": item.get("source_type", "unknown"),
                "trust_tier": item.get("trust_tier", "unverified"), "source_url": item.get("source_url", ""),
                "source_snippet": item.get("source_snippet", ""), "metadata": item.get("metadata", {}),
            })

        pdf_only = mode == "pdf_only"
        citation_metadata = build_citation_metadata(source_materials, pdf_only=pdf_only)

        conflict_alerts = []
        if hybrid_results and web_results:
            conflict_alerts = detect_conflicts(hybrid_results, web_results, citation_metadata, pdf_only=pdf_only)

        return {
            "top_k_chunks": reranked, "source_materials": source_materials,
            "research_results": [item.get("text", "") for item in reranked],
            "web_search_used": web_search_used, "material_pool_frozen": True,
            "citation_metadata": citation_metadata, "conflict_alerts": conflict_alerts,
        }

    # ============================================================
    #  【优化】一次性联网搜索：在遍历子任务之前，先批量搜索所有需要联网的子任务
    #  仅联网一次，避免每个子任务独立搜索导致的多次联网
    # ============================================================
    web_search_queries = []
    for st in sub_tasks:
        st_text = st.get("sub_query", st.get("task_text", st.get("text", "")))
        st_route = st.get("route_tag", "pdf_web")
        if mode in ("web_only", "pdf_web") and st_route in ("web_only", "pdf_web"):
            web_search_queries.append(st_text)

    # 一次性批量联网搜索（仅当需要联网时）
    batch_web_results = {}
    if web_search_queries and mode in ("web_only", "pdf_web"):
        # 将所有子任务查询合并为一个综合查询串，一次搜索
        merged_query = "；".join(web_search_queries)
        logger.info(f"   🌐【一次性批量搜索】{len(web_search_queries)} 个子任务合并为一次搜索")
        raw_web_results = _execute_web_search(merged_query)
        # 为每个子任务分配搜索结果（所有子任务共享同一批结果，但各自用 rerank 过滤）
        for q in web_search_queries:
            batch_web_results[q] = list(raw_web_results)  # 浅拷贝引用
        logger.info(f"   🌐 批量搜索完成: 共 {len(raw_web_results)} 条原始结果，共享给 {len(web_search_queries)} 个子任务")
    else:
        logger.info(f"   🌐 本次无需联网搜索 (mode={mode}, web_search_queries={len(web_search_queries)})")

    # has sub_tasks: iterate
    logger.info(f"sub_tasks: {len(sub_tasks)}")
    sub_task_results = []
    all_retrieved_chunks = []
    relevant_count = 0
    insufficient_count = 0
    irrelevant_count = 0

    for idx, sub_task in enumerate(sub_tasks):
        sub_task_text = sub_task.get("sub_query", sub_task.get("task_text", sub_task.get("text", "")))
        route_tag = sub_task.get("route_tag", "pdf_web")
        logger.info(f"subtask {idx+1}/{len(sub_tasks)}: {sub_task_text[:40]} route={route_tag}")

        # 获取预搜索的联网结果（如果有）
        pre_fetched_web = batch_web_results.get(sub_task_text, []) if web_search_queries else []

        result = _retrieve_for_sub_task(
            sub_task_text, route_tag, state, pdf_collection, cleaned_chunks,
            pre_fetched_web_results=pre_fetched_web,
        )
        sub_task_results.append(result)

        rel = result.get("relevance", "irrelevant")
        if rel == "relevant":
            relevant_count += 1
            all_retrieved_chunks.extend(result.get("retrieved_chunks", []))
        elif rel == "insufficient":
            insufficient_count += 1
            all_retrieved_chunks.extend(result.get("retrieved_chunks", []))
        else:
            irrelevant_count += 1

    if irrelevant_count == len(sub_tasks):
        logger.warning(f"all {len(sub_tasks)} sub_tasks irrelevant -> early terminate")
        state["retrieval_relevance"] = "irrelevant"
        state["sub_task_results"] = sub_task_results
        # 场景2/9: 子任务全部不相关→早停，不进analyst+writer
        return {
            "top_k_chunks": [], "source_materials": [], "research_results": [],
            "web_search_used": False, "material_pool_frozen": True,
            "terminate_reason": "ALL_SUB_TASKS_IRRELEVANT",
            "retrieval_relevance": "irrelevant",
            "sub_task_results": sub_task_results,
            "early_terminate": True,
            "error_message": "📄 当前文档内容与您的调研需求不相关，无法生成有效分析。请尝试：1）上传更相关的文档 2）切换至「PDF+联网」或「纯联网」模式",
            "info_limitation_note": "文档内容与需求不相关，请切换模式或更换文档",
        }

    reranked = all_retrieved_chunks[:12]
    state["retrieval_relevance"] = "insufficient" if relevant_count == 0 else "relevant"

    logger.info(f"summary: {relevant_count} relevant, {insufficient_count} insufficient, {irrelevant_count} irrelevant")
    logger.info(f"aggregated: {len(reranked)} chunks")

    source_materials = []
    for i, item in enumerate(reranked):
        source_materials.append({
            "text": item.get("text", ""), "source_index": item.get("source_index", i),
            "rerank_score": item.get("rerank_score", 0), "source_type": item.get("source_type", "unknown"),
            "trust_tier": item.get("trust_tier", "unverified"), "source_url": item.get("source_url", ""),
            "source_snippet": item.get("source_snippet", ""), "metadata": item.get("metadata", {}),
        })

    pdf_only = mode == "pdf_only"
    citation_metadata = build_citation_metadata(source_materials, pdf_only=pdf_only)

    conflict_alerts = []
    has_pdf_results = any(r.get("source_type") == "pdf" for r in reranked)
    has_web_results = any(r.get("source_type") == "web" for r in reranked)
    if has_pdf_results and has_web_results:
        conflict_alerts = detect_conflicts(
            [r for r in reranked if r.get("source_type") == "pdf"],
            [r for r in reranked if r.get("source_type") == "web"],
            citation_metadata, pdf_only=pdf_only,
        )

    state["sub_task_results"] = sub_task_results
    web_search_used = any(r.get("source_type") == "web" for r in reranked)

    return {
        "top_k_chunks": reranked, "source_materials": source_materials,
        "research_results": [item.get("text", "") for item in reranked],
        "web_search_used": web_search_used, "material_pool_frozen": True,
        "citation_metadata": citation_metadata, "conflict_alerts": conflict_alerts,
        "sub_task_results": sub_task_results,
    }
