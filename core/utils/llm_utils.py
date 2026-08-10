"""LLM 通用工具函数"""

import json
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
    """从 LLM 响应中提取文本内容（兼容 AIMessage 嵌套 + ChatGenerationChunk 流式 chunk）"""
    # 兼容 ChatGenerationChunk（流式 chunk，文本在 .text 属性上）
    if hasattr(response, 'text'):
        return str(response.text)

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