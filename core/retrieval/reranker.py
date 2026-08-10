import json
from typing import Any, Dict, List, Optional

from core.llm.provider import get_llm
from langchain_core.prompts import ChatPromptTemplate


# ============================================================
#  交叉编码重排序（Cross-Encoder Style）
# ============================================================


def _llm_rerank_structured(
    query: str,
    candidates: List[Dict[str, Any]],
    model_mode: str,
    model_name: str = "",
) -> List[Dict[str, Any]]:
    """
    使用 LLM 进行交叉编码深度重排序。
    一次性对所有候选片段做批量相关性判断，输出相关性标签。
    """
    llm = get_llm(temperature=0.1, model_mode=model_mode, model_name=model_name)

    candidate_lines = []
    for i, c in enumerate(candidates):
        text = c.get("text", "")[:600]
        candidate_lines.append(f"[{i}] {text}")
    candidates_str = "\n\n".join(candidate_lines)

    system_prompt = (
        "你是一个文本相关性评估专家。对给定的查询和一系列文本片段，"
        "请判断每个片段与查询的相关性。"
    )

    prompt = ChatPromptTemplate.from_template(
        "查询：{query}\n\n"
        "候选文本片段：\n{candidates}\n\n"
        "请逐个评估每个片段的相关性，输出 JSON 格式结果：\n"
        '{{"results": [\n'
        '  {{"index": 0, "relevance": "相关"}},\n'
        '  {{"index": 1, "relevance": "不相关"}},\n'
        '  {{"index": 2, "relevance": "高度相关"}}\n'
        "]}}\n\n"
        "相关性标签只能为以下三种之一：\n"
        '- "高度相关"：与查询核心一致，提供了关键信息\n'
        '- "相关"：与查询部分相关，提供辅助信息\n'
        '- "不相关"：与查询无关或语义漂移\n\n'
        "仅输出 JSON，不要多余文字。"
    )

    chain = prompt | llm
    resp = chain.invoke({"query": query, "candidates": candidates_str})
    content = _extract_llm_content(resp)

    label_map = {}
    try:
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            data = json.loads(content[start:end])
            for item in data.get("results", []):
                idx = item.get("index")
                label = item.get("relevance", "不相关")
                if idx is not None:
                    label_map[int(idx)] = label
    except Exception:
        pass

    label_weight = {"高度相关": 3, "相关": 2, "不相关": 1}

    scored_results = []
    for i, candidate in enumerate(candidates):
        # 修复：复制原始 dict，保留所有字段（source_url, cleaned_chunks, cleaned_full_text, trust_tier 等）
        result = dict(candidate)
        text = candidate.get("text", "")[:800]
        label = label_map.get(i, "不相关")
        rank_weight = label_weight.get(label, 1)

        result["text"] = text
        result["rerank_score"] = rank_weight
        result["relevance_label"] = label
        # 保留原始 source_type（"web" / "pdf"），不覆盖为 "reranked"
        result["source_type"] = candidate.get("source_type", "reranked")
        scored_results.append(result)

    scored_results.sort(key=lambda x: x["rerank_score"], reverse=True)

    filtered = [r for r in scored_results if r["relevance_label"] != "不相关"]
    if not filtered and scored_results:
        filtered = scored_results[:1]

    return filtered


# ============================================================
#  辅助函数
# ============================================================

def _parse_web_results(raw_results: Any) -> List[Dict[str, Any]]:
    """将 Tavily 搜索结果解析为独立条目列表"""
    entries = []
    if isinstance(raw_results, list):
        for item in raw_results:
            if isinstance(item, dict):
                title = item.get("title", "")
                url = item.get("url", "")
                content = item.get("content", "")
                text = f"[{title}]({url})\n{content}" if title and url else str(item)
                entries.append({
                    "source": "web",
                    "title": title,
                    "url": url,
                    "content": content,
                    "text": text,
                })
            elif isinstance(item, str):
                entries.append({"source": "web", "title": "", "url": "", "content": item, "text": item})
            else:
                entries.append({"source": "web", "title": "", "url": "", "content": str(item), "text": str(item)})
    elif isinstance(raw_results, str):
        entries.append({"source": "web", "title": "", "url": "", "content": raw_results, "text": raw_results})
    else:
        entries.append({"source": "web", "title": "", "url": "", "content": str(raw_results), "text": str(raw_results)})
    return entries


def _llm_rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    model_mode: str,
    model_name: str = "",
) -> List[Dict[str, Any]]:
    """使用 LLM 对候选条目进行相关度打分并排序"""
    llm = get_llm(temperature=0.1, model_mode=model_mode, model_name=model_name)

    candidate_lines = []
    for i, c in enumerate(candidates):
        snippet = c.get("text", "")[:300]
        candidate_lines.append(f"[{i}] {snippet}")
    candidates_str = "\n\n".join(candidate_lines)

    prompt = ChatPromptTemplate.from_template(
        "你是一个搜索结果排序专家。给定一个搜索查询和若干候选结果，"
        "请评估每个结果与查询的相关性，输出 JSON 格式的排序结果。\n\n"
        "查询：{query}\n\n"
        "候选结果列表：\n{candidates}\n\n"
        "请按以下 JSON 格式输出（不要带 markdown 代码块标记）：\n"
        '{{"scores": [{{"index": 0, "relevance": 9}}, {{"index": 1, "relevance": 5}}]}}\n\n'
        "说明：\n"
        "- index 对应候选结果列表中的序号\n"
        "- relevance 是一个 1-10 的整数，10 表示最相关\n"
        "- 仅输出 JSON，不要额外文字"
    )

    chain = prompt | llm
    response = chain.invoke({"query": query, "candidates": candidates_str})

    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = " ".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content)
    content = str(content)

    scores = {}
    try:
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            json_str = content[start:end]
            data = json.loads(json_str)
            score_list = data.get("scores", data) if isinstance(data, dict) else data
            for item in score_list:
                if isinstance(item, dict):
                    idx = item.get("index")
                    score = item.get("relevance", item.get("score", 5))
                    if idx is not None:
                        scores[int(idx)] = int(score)
    except Exception:
        pass

    for i, c in enumerate(candidates):
        c["_score"] = scores.get(i, 5)

    return sorted(candidates, key=lambda x: x.get("_score", 0), reverse=True)


def _format_merged(web_entries: List[Dict[str, Any]], pdf_texts: List[str]) -> str:
    """将重排后的结果重新格式化为字符串"""
    parts = []
    if web_entries:
        web_texts = [e["text"] for e in web_entries]
        parts.append("【网络搜索结果】\n" + "\n\n".join(web_texts))
    if pdf_texts:
        parts.append("【PDF 参考材料】\n" + " | ".join(pdf_texts))
    return "\n\n".join(parts)


def _extract_llm_content(response: Any) -> str:
    """从 LLM 响应中提取文本内容"""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = " ".join(str(c.get("text", "")) if isinstance(c, dict) else str(c) for c in content)
    return str(content)
