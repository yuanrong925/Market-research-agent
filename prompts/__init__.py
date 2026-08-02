"""
提示词管理器

从 prompts/*.yaml 文件中动态加载提示词，支持运行时热加载。
"""
import os
import yaml
from typing import Dict, Any, Optional

# 缓存已加载的提示词
_prompt_cache: Dict[str, Dict[str, Any]] = {}


def _get_prompts_dir() -> str:
    """返回 prompts 目录的绝对路径"""
    return os.path.dirname(os.path.abspath(__file__))


def load_prompt_file(filename: str) -> Dict[str, Any]:
    """加载单个 YAML 提示词文件"""
    filepath = os.path.join(_get_prompts_dir(), filename)
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"提示词文件不存在: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def get_prompt(prompt_key: str, filename: Optional[str] = None, **kwargs) -> str:
    """
    获取指定提示词文本，支持变量插值。
    
    参数:
      prompt_key: 提示词在 YAML 中的键名（如 'system_prompt'）
      filename: YAML 文件名（如 'analyst.yaml'），不指定则全局搜索
      **kwargs: 用于格式化提示词的变量
    
    返回:
      格式化后的提示词字符串
    """
    if filename:
        data = load_prompt_file(filename)
    else:
        # 搜索所有 YAML 文件
        prompts_dir = _get_prompts_dir()
        for fname in os.listdir(prompts_dir):
            if fname.endswith(('.yaml', '.yml')):
                data = load_prompt_file(fname)
                if prompt_key in data:
                    break
        else:
            raise KeyError(f"提示词 '{prompt_key}' 未找到")

    prompt_text = data.get(prompt_key)
    if prompt_text is None:
        raise KeyError(f"提示词文件 '{filename or '?'}' 中未找到键 '{prompt_key}'")

    if kwargs:
        prompt_text = prompt_text.format(**kwargs)

    return prompt_text


def reload_all():
    """清空缓存，强制重新加载所有提示词"""
    _prompt_cache.clear()


def list_prompts() -> Dict[str, list]:
    """列出所有可用的提示词文件及键名"""
    result = {}
    prompts_dir = _get_prompts_dir()
    for fname in sorted(os.listdir(prompts_dir)):
        if fname.endswith(('.yaml', '.yml')):
            data = load_prompt_file(fname)
            result[fname] = list(data.keys())
    return result
