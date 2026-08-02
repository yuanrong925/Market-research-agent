"""
【市场调研专属】规划节点 — 前置一次性任务拆解

核心业务逻辑（市场调研独有，通用问答系统不需要）：
  1. LLM 接收用户原始调研需求，拆分为多个独立子调研维度
  2. 结构化标准 JSON 输出字段：sub_query、route_tag、judge_reason、priority
  3. route_tag 判定硬性规则（写入节点 Prompt）
     - pdf_only：仅需解读内部 PDF 静态资料
     - web_only：需要强时效性政策/最新行业数据
     - pdf_web：需结合内部基线数据与外网最新信息交叉对比
  4. 仅做前置一次性任务拆解，不做运行时动态重规划（由全局熔断机制管控）

架构预留拓展注释：
  - 后续可扩展：重规划逻辑（失败重试→动态调整子任务）、子任务依赖图（DAG调度）
"""

import json
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

from core.llm.provider import get_llm
from core.utils.llm_utils import extract_text_content
from core.utils.logger import get_logger

from business.market_research.state import AgentState
from business.market_research.prompts import get_prompt

logger = get_logger(__name__)


def plan_node(state: AgentState) -> Dict[str, Any]:
    """
    规划节点：将用户调研需求拆解为多个子调研维度。

    仅做前置一次性任务拆解，不做运行时动态重规划。
    重规划逻辑统一由全局熔断机制管控。

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态，包含 sub_tasks 列表
    """
    task = state.get("task", "")
    if not task:
        logger.warning("⚠️ [PlanNode] 任务为空，跳过拆解")
        return {"sub_tasks": []}

    # 获取用户选择的搜索模式
    manual_web_search_mode = state.get("manual_web_search_mode", "auto").lower()

    logger.info("📋 [PlanNode] 开始拆解调研需求...")
    logger.info(f"   [PlanNode] 原始需求: {task[:80]}...")
    logger.info(f"   [PlanNode] 用户搜索模式: {manual_web_search_mode}")
    _plan_start = __import__("time").time()

    llm = get_llm(temperature=0.3, model_mode=state.get("model_mode"))

    system_prompt = get_prompt("system_prompt", "market_planning.yaml")

    # 将用户选择的搜索模式传递给 LLM
    mode_hint = ""
    if manual_web_search_mode == "disabled":
        mode_hint = "\n\n【重要约束】用户已选择「仅 PDF」模式，禁止联网搜索。所有子任务的 route_tag 必须全部设置为 pdf_only，不允许出现 web_only 或 pdf_web。"
    elif manual_web_search_mode == "auto":
        mode_hint = "\n\n【当前模式】用户已选择「PDF + 联网」模式，按正常规则分配 route_tag。"
    elif manual_web_search_mode == "enabled":
        mode_hint = "\n\n【当前模式】用户已选择「纯联网」模式，仅联网搜索。所有子任务的 route_tag 必须全部设置为 web_only，不允许出现 pdf_only 或 pdf_web。"

    prompt = [
        SystemMessage(content=system_prompt + mode_hint),
        HumanMessage(content=f"请对以下调研需求进行任务拆解：\n\n{task}"),
    ]

    try:
        resp = llm.invoke(prompt)
        content = extract_text_content(resp)

        # 解析 JSON 输出
        sub_tasks = []
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            data = json.loads(content[start:end])
            sub_tasks = data.get("sub_tasks", [])

        # 数据校验与兜底
        if not sub_tasks:
            logger.warning("   ⚠️ LLM 未返回有效子任务，使用兜底方案")
            sub_tasks = _fallback_planning(task)

        # 按优先级排序
        sub_tasks.sort(key=lambda x: x.get("priority", 999))

        # 安全兜底：根据用户搜索模式强制覆盖 route_tag
        if manual_web_search_mode == "disabled":
            for st in sub_tasks:
                st["route_tag"] = "pdf_only"
                st["judge_reason"] = st.get("judge_reason", "") + "（用户已选择仅 PDF 模式，强制 pdf_only）"
        elif manual_web_search_mode == "enabled":
            for st in sub_tasks:
                st["route_tag"] = "web_only"
                st["judge_reason"] = st.get("judge_reason", "") + "（用户已选择纯联网模式，强制 web_only）"

        _plan_elapsed = __import__("time").time() - _plan_start
        logger.info(f"   ✅ [PlanNode] 拆解完成: {len(sub_tasks)} 个子任务, 耗时: {_plan_elapsed:.2f}s")
        for i, st in enumerate(sub_tasks):
            logger.info(f"       [{i+1}] p={st.get('priority', '?')} | {st.get('route_tag', '?')} | {st.get('sub_query', '')[:50]}...")

        return {
            "sub_tasks": sub_tasks,
            "planning_completed": True,
        }

    except Exception as e:
        logger.error(f"   ❌ [PlanNode] 拆解失败: {e}")
        # 兜底方案
        fallback = _fallback_planning(task, manual_web_search_mode)
        return {
            "sub_tasks": fallback,
            "planning_completed": True,
        }


def _fallback_planning(task: str, manual_web_search_mode: str = "auto") -> List[Dict[str, Any]]:
    """
    兜底方案：当 LLM 解析失败时，生成一个基本的子任务列表。

    根据用户选择的搜索模式，决定 route_tag 的取值。
    """
    if manual_web_search_mode == "disabled":
        route_tag = "pdf_only"
    elif manual_web_search_mode == "enabled":
        route_tag = "web_only"
    else:
        route_tag = "pdf_web"

    return [
        {
            "sub_query": f"行业概况与背景分析：{task}",
            "route_tag": route_tag,
            "judge_reason": f"兜底方案：用户选择 {manual_web_search_mode} 模式，自动生成的标准子任务",
            "priority": 1,
        },
        {
            "sub_query": f"核心维度分析：{task}",
            "route_tag": route_tag,
            "judge_reason": f"兜底方案：用户选择 {manual_web_search_mode} 模式，自动生成的标准子任务",
            "priority": 2,
        },
        {
            "sub_query": f"延伸分析：{task}",
            "route_tag": route_tag,
            "judge_reason": f"兜底方案：用户选择 {manual_web_search_mode} 模式，自动生成的标准子任务",
            "priority": 3,
        },
    ]