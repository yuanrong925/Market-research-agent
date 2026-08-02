"""
会话状态管理器（多轮对话支持）

设计原则：
  - 会话记忆是"只读上下文"——包含历史报告、冻结素材池、对话记录
  - 追问不重新检索，不修改原始报告，仅生成补充回答
  - 会话 24 小时自动过期
"""
import time
import uuid
from typing import Any, Dict, List, Optional


# 内存会话存储（生产环境建议换 Redis）
_sessions: Dict[str, Dict[str, Any]] = {}

# 会话过期时间（秒）
SESSION_TTL = 86400  # 24 小时


def create_session(
    task: str,
    final_report: Optional[Dict] = None,
    top_k_chunks: Optional[List[Dict]] = None,
    source_materials: Optional[List[Dict]] = None,
    analyst_outline: Optional[List[Dict]] = None,
    web_search_used: bool = False,
) -> str:
    """创建新会话，返回 session_id"""
    session_id = uuid.uuid4().hex[:12]
    _sessions[session_id] = {
        "task": task,
        "final_report": final_report or {},
        "top_k_chunks": top_k_chunks or [],
        "source_materials": source_materials or [],
        "analyst_outline": analyst_outline or [],
        "web_search_used": web_search_used,
        "conversation": [],  # 对话历史: [{"role": "user"|"assistant", "content": str}]
        "created_at": time.time(),
        "last_access": time.time(),
    }
    _clean_expired()
    return session_id


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """获取会话数据，自动续期"""
    session = _sessions.get(session_id)
    if session is None:
        return None
    if time.time() - session["created_at"] > SESSION_TTL:
        del _sessions[session_id]
        return None
    session["last_access"] = time.time()
    return session


def append_conversation(session_id: str, role: str, content: str) -> bool:
    """追加对话记录"""
    session = get_session(session_id)
    if session is None:
        return False
    session["conversation"].append({"role": role, "content": content})
    return True


def get_conversation_history(session_id: str) -> List[Dict[str, str]]:
    """获取对话历史"""
    session = get_session(session_id)
    if session is None:
        return []
    return session["conversation"]


def _clean_expired():
    """清理过期会话"""
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s["created_at"] > SESSION_TTL]
    for sid in expired:
        del _sessions[sid]