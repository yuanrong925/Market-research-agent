"""LLM 通用工具函数"""

import json
import time
from typing import Any, List


def extract_llm_content(response: Any) -> str:
    """从 LLM 响应中提取文本内容"""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        content = " ".join(
            str(c.get("text", "")) if isinstance(c, dict) else str(c)
            for c in content
        )
    return str(content)


def extract_text_content(response: Any) -> str:
    """从 LLM 响应中提取文本内容（兼容 AIMessage 嵌套）"""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if "text" in item:
                    parts.append(str(item["text"]))
                elif "content" in item:
                    parts.append(str(item["content"]))
                else:
                    parts.append(json.dumps(item, ensure_ascii=False))
            else:
                parts.append(str(item))
        return "".join(parts)
    if isinstance(content, dict):
        if "text" in content:
            return str(content["text"])
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def is_stream_finished(chunk: Any) -> bool:
    """
    检测 LLM 流式 chunk 是否包含流结束标记。
    兼容 OpenAI / Anthropic / Ollama / LangChain 多种格式。

    返回 True 表示流已结束，应退出循环。
    """
    # --- 方案 1: OpenAI / LangChain ChatOpenAI 格式 ---
    # chunk.choices[0].finish_reason 为 "stop" 或 "length"
    if hasattr(chunk, "choices") and chunk.choices:
        finish_reason = getattr(chunk.choices[0], "finish_reason", None)
        if finish_reason is not None:
            return True

    # --- 方案 2: OpenAI raw dict 格式（如某些代理 / 流式透传）---
    if isinstance(chunk, dict):
        choices = chunk.get("choices", [])
        if choices:
            finish_reason = choices[0].get("finish_reason")
            if finish_reason is not None:
                return True

    # --- 方案 3: Anthropic 格式 ---
    if hasattr(chunk, "type") and chunk.type == "message_stop":
        return True
    if isinstance(chunk, dict) and chunk.get("type") == "message_stop":
        return True

    # --- 方案 4: Ollama ChatOllama 格式 ---
    if hasattr(chunk, "done") and chunk.done is True:
        return True
    if isinstance(chunk, dict) and chunk.get("done") is True:
        return True

    # --- 方案 5: LangChain AIMessageChunk 中 usage_metadata 出现表示结束 ---
    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata is not None:
        return True

    # --- 方案 6: response_metadata 包含 finish_reason ---
    if hasattr(chunk, "response_metadata"):
        meta = chunk.response_metadata or {}
        if meta.get("finish_reason") is not None:
            return True
        if meta.get("done") is True:
            return True

    return False
