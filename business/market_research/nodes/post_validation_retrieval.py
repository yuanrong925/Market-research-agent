"""
【Chunk 校验后置 —— 定向二次检索节点】

当 chunk_validation 通过数 < 5 条时，分析缺失的子主题方向，
执行定向二次联网检索（只搜缺失部分，不全面搜索），
然后重新校验。

最多执行 2 轮二次检索。
"""

import json
import time
from typing import Any, Dict, List

from core.utils.logger import get_logger
from core.config import get_config
from core.search.provider import get_search_provider
from business.market_research.utils.material_utils import build_web_query, classify_trust_tier
from business.market_research.utils.web_cleaner import clean_webpages_batch
from business.market_research.utils.constants import MAX_WEB_PAGES_TO_CLEAN

logger = get_logger(__name__)


def _identify_missing_sub_topics(
    sub_tasks: List[Dict],
    source_materials: List[Dict],
    top_k_chunks: List[Dict],
) -> List[str]:
    """
    分析哪些子任务方向素材不足（<2 条有效 chunk），返回需要补充检索的子查询。
    """
    if not sub_tasks:
        return []

    # 统计每个子任务在 source_materials 中出现的次数
    sub_task_texts = []
    for st in sub_tasks:
        st_text = st.get("sub_query", st.get("task_text", st.get("text", "")))
        sub_task_texts.append(st_text)

    # 将 source_materials 中的文本全部拼接
    all_text = " ".join([m.get("text", "") for m in source_materials])

    missing = []
    for st_text in sub_task_texts:
        if not st_text:
            continue
        # 简单关键词匹配：子任务前 20 个字符在素材中出现次数
        keywords = st_text[:20].strip()
        count = all_text.count(keywords) if keywords else 0
        if count < 2:
            missing.append(st_text)

    # 如果全部缺失，只取前 2 个最需要补充的
    if len(missing) > 2:
        missing = missing[:2]

    return missing


def _execute_targeted_web_search(
    missing_queries: List[str],
    existing_urls: set,
) -> List[Dict]:
    """
    执行定向联网搜索，只搜缺失部分，避免全面搜索。

    返回新的 web_results（不包含已有 URL 的重复结果）。
    """
    cfg = get_config()
    new_results = []

    for query in missing_queries:
        logger.info(f"   🔎 定向二次检索: {query[:40]}...")
        try:
            search_provider = get_search_provider()
            # 使用更具体的查询，减少无关结果
            refined_query = build_web_query(query, round_num=2, last_round_success=True)
            search_response = search_provider.search(refined_query, max_results=3)

            for sidx, item in enumerate(search_response):
                url = item.get("url", "")
                if url in existing_urls:
                    continue  # 跳过已有结果

                snippet = item.get("content", item.get("snippet", ""))
                trust = classify_trust_tier(url, snippet)
                new_results.append({
                    "text": snippet[:800],
                    "score": 0.7 if trust == "verified" else 0.5,
                    "source_index": sidx,
                    "source_type": "web",
                    "trust_tier": trust,
                    "source_url": url,
                    "source_snippet": snippet[:200],
                    "search_round": 2,  # 标记为二次检索
                    "cleaned_chunks": [],
                    "fetch_status": "pending",
                })

            logger.info(f"      获得 {len(search_response)} 条新结果")
        except Exception as e:
            logger.warning(f"   ⚠️ 定向二次检索失败: {e}")

    # 过滤低质量
    new_results = [r for r in new_results if r.get("trust_tier") != "low_quality"]

    # 清洗网页
    if new_results:
        logger.info(f"   🌐 清洗 {len(new_results)} 个新网页...")
        max_pages = getattr(cfg, "max_web_pages_to_clean", MAX_WEB_PAGES_TO_CLEAN)
        all_cleaned = clean_webpages_batch(new_results, max_pages=max_pages)

        for result in new_results:
            url = result.get("source_url", "")
            matching = [c for c in all_cleaned if c.get("source_url", "") == url]
            if matching:
                result["cleaned_chunks"] = matching
                result["fetch_status"] = matching[0].get("fetch_status", "cleaned")
                full_text = "\n\n".join([c["text"] for c in matching])
                if full_text and len(full_text) > len(result.get("text", "")):
                    result["text"] = full_text[:8000]
                    result["cleaned_full_text"] = full_text
            else:
                result["fetch_status"] = "fallback"

    return new_results


def post_validation_retrieval_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    后置定向二次检索节点。

    触发条件：
      - chunk_validation 通过数 < 5
      - 当前模式允许联网（pdf_web 或 web_only）
      - 二次检索轮次 < 2

    执行逻辑：
      1. 分析缺失的子主题方向
      2. 定向联网搜索（只搜缺失部分）
      3. 将新结果合并到 top_k_chunks 和 source_materials
      4. 更新 validation_retry_count

    输出：
      - validation_retry_count: 更新后的重试次数
      - top_k_chunks: 合并后的完整列表
      - source_materials: 合并后的完整列表
      - need_revalidation: True（通知下游重新校验）
    """
    source_materials = state.get("source_materials", [])
    top_k_chunks = state.get("top_k_chunks", [])
    sub_tasks = state.get("sub_tasks", [])
    validation_retry_count = state.get("validation_retry_count", 0)
    manual_mode = state.get("manual_web_search_mode", "auto").lower()
    mode = "pdf_only" if manual_mode in ("disabled", "pdf_only") else "pdf_web" if manual_mode in ("auto", "pdf_web") else "web_only"

    logger.info(f"🔍 [PostValidationRetrieval] 开始定向二次检索 (第 {validation_retry_count + 1} 轮)...")

    # 检查是否需要二次检索
    if mode == "pdf_only":
        logger.info("   [PostValidationRetrieval] 仅 PDF 模式，跳过二次检索")
        return {"validation_retry_count": validation_retry_count, "need_revalidation": False}

    if validation_retry_count >= 2:
        logger.info(f"   [PostValidationRetrieval] 二次检索已达上限 ({validation_retry_count} 轮)，跳过")
        return {"validation_retry_count": validation_retry_count, "need_revalidation": False}

    passed_count = len(source_materials)
    if passed_count >= 2:
        logger.info(f"   [PostValidationRetrieval] 素材充足 ({passed_count} 条)，无需二次检索")
        return {"validation_retry_count": validation_retry_count, "need_revalidation": False}

    # 分析缺失的子主题
    missing_queries = _identify_missing_sub_topics(sub_tasks, source_materials, top_k_chunks)
    if not missing_queries:
        logger.info("   [PostValidationRetrieval] 无缺失子主题，跳过二次检索")
        return {"validation_retry_count": validation_retry_count, "need_revalidation": False}

    # 收集已有 URL 去重
    existing_urls = set()
    for chunk in top_k_chunks:
        url = chunk.get("source_url", "")
        if url:
            existing_urls.add(url)

    # 执行定向搜索
    logger.info(f"   [PostValidationRetrieval] 需要补充 {len(missing_queries)} 个方向: {[q[:30] for q in missing_queries]}")
    new_results = _execute_targeted_web_search(missing_queries, existing_urls)

    if not new_results:
        logger.info("   [PostValidationRetrieval] 二次检索未获得新结果")
        return {
            "validation_retry_count": validation_retry_count + 1,
            "need_revalidation": False,
        }

    logger.info(f"   [PostValidationRetrieval] 获得 {len(new_results)} 条新结果")

    # 合并到 top_k_chunks
    existing_top_k = list(top_k_chunks)
    for nr in new_results:
        existing_top_k.append(nr)

    # 构建新的 source_materials
    new_source_materials = []
    for i, item in enumerate(existing_top_k):
        new_source_materials.append({
            "text": item.get("text", ""),
            "source_index": item.get("source_index", i),
            "rerank_score": item.get("rerank_score", 0),
            "source_type": item.get("source_type", "unknown"),
            "trust_tier": item.get("trust_tier", "unverified"),
            "source_url": item.get("source_url", ""),
            "source_snippet": item.get("source_snippet", ""),
            "metadata": item.get("metadata", {}),
        })

    new_validation_retry_count = validation_retry_count + 1
    logger.info(f"   [PostValidationRetrieval] 二次检索完成: 新素材 {len(new_results)} 条, 总素材 {len(new_source_materials)} 条, 轮次 {new_validation_retry_count}")

    return {
        "top_k_chunks": existing_top_k,
        "source_materials": new_source_materials,
        "validation_retry_count": new_validation_retry_count,
        "need_revalidation": True,  # 通知下游重新校验
    }