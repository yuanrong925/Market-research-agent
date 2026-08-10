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

    v2 修复：
      1. auto（PDF+联网）模式 + 无PDF上传 → 不再阻断，强制降级为纯联网
         route_tag 全部设为 web_only，子任务正常流转
      2. disabled（仅PDF）模式 + 无PDF上传 → 阻断
      3. 所有子任务的 route_tag 在前端选择模式约束下强制覆盖

    Args:
        state: 当前工作流状态

    Returns:
        更新后的状态，包含 sub_tasks 列表
    """
    task = state.get("task", "")
    if not task:
        logger.warning("⚠️ [PlanNode] 任务为空，跳过拆解")
        return {"sub_tasks": []}

    manual_web_search_mode = state.get("manual_web_search_mode", "auto").lower()
    has_pdf = bool(state.get("pdf_path", ""))

    # ============================================================
    #  前置拦截（仅拦截真正无法执行的模式）
    # ============================================================
    if manual_web_search_mode == "disabled" and not has_pdf:
        logger.warning("🚫 [PlanNode] 仅PDF模式但未上传PDF")
        return {
            "sub_tasks": [],
            "planning_completed": True,
            "terminate_reason": "NO_PDF_IN_PDF_ONLY_MODE",
            "error_message": "仅PDF模式必须上传PDF文档，请上传后重试或切换至其他模式",
        }

    # ============================================================
    #  auto + 无PDF → 自动降级为纯联网（不阻断）
    # ============================================================
    if manual_web_search_mode == "auto" and not has_pdf:
        logger.info("   [PlanNode] PDF+联网模式但无PDF上传，自动降级为纯联网")
        # 强制子任务 route_tag 为 web_only
        forced_route_tag = "web_only"
        # 记录降级通知
        state["web_only_with_pdf_notice"] = (
            "您选择了【PDF+联网】模式但未上传PDF文档，系统已自动降级为【纯联网】模式，"
            "仅基于公开网络信息进行分析。如需上传文档，请重新发起请求时附上PDF文件。"
        )
    elif manual_web_search_mode == "disabled":
        forced_route_tag = "pdf_only"
    elif manual_web_search_mode == "enabled":
        forced_route_tag = "web_only"
    else:
        forced_route_tag = None  # auto + 有PDF，正常分配

    # 关键词粗筛（仅PDF模式）
    if manual_web_search_mode == "disabled":
        NEED_WEB_KEYWORDS = [
            "最新", "趋势", "动态", "近期", "当前", "现状",
            "政策", "法规", "监管", "合规", "标准",
            "竞争格局", "市场竞争", "行业排名", "头部企业", "市场占有率",
            "增长率", "增速", "同比增长", "市场份额", "占比",
            "融资", "上市", "IPO", "投资", "并购",
            "2025", "2026", "2027", "2028", "2029", "2030",
            "预测", "展望", "未来", "前景", "机遇",
        ]
        task_lower = task.lower()
        matched_keywords = [kw for kw in NEED_WEB_KEYWORDS if kw in task_lower]
        if matched_keywords:
            logger.warning(f"🚫 [PlanNode] 仅PDF模式但任务需联网")
            return {
                "sub_tasks": [],
                "planning_completed": True,
                "terminate_reason": "MODE_CONFLICT",
                "error_message": "【模式冲突】当前模式为【仅PDF】，但您的调研需求需要联网获取最新信息。请切换至【PDF+联网】模式或【纯联网】模式后再试",
            }

    logger.info("📋 [PlanNode] 开始拆解调研需求...")
    logger.info(f"   [PlanNode] 原始需求: {task[:80]}...")
    logger.info(f"   [PlanNode] 用户搜索模式: {manual_web_search_mode}, 有PDF: {has_pdf}")
    if forced_route_tag:
        logger.info(f"   [PlanNode] 强制 route_tag: {forced_route_tag}")
    _plan_start = __import__("time").time()

    llm = get_llm(temperature=0.3, model_mode=state.get("model_mode"), model_name=state.get("model_name", ""))
    system_prompt = get_prompt("system_prompt", "market_planning.yaml")

    # 构建模式约束提示
    if forced_route_tag == "web_only":
        mode_hint = (
            "\n\n【重要约束】当前模式为「纯联网」模式（无PDF文档），"
            "所有子任务的 route_tag 必须全部设置为 web_only，不允许出现 pdf_only 或 pdf_web。"
        )
    elif forced_route_tag == "pdf_only":
        mode_hint = (
            "\n\n【重要约束】用户已选择「仅 PDF」模式，禁止联网搜索。"
            "所有子任务的 route_tag 必须全部设置为 pdf_only，不允许出现 web_only 或 pdf_web。"
        )
    elif manual_web_search_mode == "auto":
        mode_hint = "\n\n【当前模式】用户已选择「PDF + 联网」模式，按正常规则分配 route_tag。"
    else:
        mode_hint = ""

    prompt = [
        SystemMessage(content=system_prompt + mode_hint),
        HumanMessage(content=f"请对以下调研需求进行任务拆解：\n\n{task}"),
    ]

    try:
        resp = llm.invoke(prompt)
        content = extract_text_content(resp)
        sub_tasks = []
        if "{" in content:
            start = content.find("{")
            end = content.rfind("}") + 1
            data = json.loads(content[start:end])
            sub_tasks = data.get("sub_tasks", [])

        if not sub_tasks:
            logger.warning("   ⚠️ LLM 未返回有效子任务，使用兜底方案")
            sub_tasks = _fallback_planning(task, forced_route_tag)

        # 强制覆盖 route_tag（如果前端模式约束了）
        if forced_route_tag:
            for st in sub_tasks:
                st["route_tag"] = forced_route_tag

        # 按优先级排序
        sub_tasks.sort(key=lambda x: x.get("priority", 999))

        # 后置拦截（仅PDF模式子任务需要联网）
        if manual_web_search_mode == "disabled" and not forced_route_tag:
            has_web_route = any(
                st.get("route_tag") in ("web_only", "pdf_web")
                for st in sub_tasks
            )
            if has_web_route:
                logger.warning("🚫 [PlanNode] 后置拦截：仅PDF模式但子任务需要联网")
                return {
                    "sub_tasks": sub_tasks,
                    "planning_completed": True,
                    "terminate_reason": "MODE_CONFLICT",
                    "error_message": "【模式冲突】当前模式为【仅PDF】，但部分子任务需要联网。请切换至【PDF+联网】模式或上传包含所需信息的PDF文档",
                }

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
        fallback = _fallback_planning(task, forced_route_tag or "web_only")
        return {
            "sub_tasks": fallback,
            "planning_completed": True,
        }


def _fallback_planning(task: str, forced_route_tag: str = None) -> List[Dict[str, Any]]:
    """
    兜底方案：当 LLM 解析失败时生成标准子任务列表。
    """
    route_tag = forced_route_tag or "web_only"

    return [
        {
            "sub_query": f"行业概况与背景分析：{task}",
            "route_tag": route_tag,
            "judge_reason": f"兜底方案：route_tag={route_tag}",
            "priority": 1,
        },
        {
            "sub_query": f"核心维度分析：{task}",
            "route_tag": route_tag,
            "judge_reason": f"兜底方案：route_tag={route_tag}",
            "priority": 2,
        },
        {
            "sub_query": f"延伸分析：{task}",
            "route_tag": route_tag,
            "judge_reason": f"兜底方案：route_tag={route_tag}",
            "priority": 3,
        },
    ]