"""Gestion des sessions pour Alex Brain."""
from collections import OrderedDict
from .config import MAX_SESSIONS, MAX_SESSION_MSGS


_sessions: dict[str, list[dict]] = OrderedDict()


def get_session(sid: str) -> list[dict]:
    if not sid:
        return []
    if sid not in _sessions:
        if len(_sessions) >= MAX_SESSIONS:
            _sessions.pop(next(iter(_sessions)))
        _sessions[sid] = []
    return _sessions[sid]


def append_session(sid: str, msg: dict) -> None:
    if not sid:
        return
    msgs = get_session(sid)
    msgs.append(msg)
    if len(msgs) > MAX_SESSION_MSGS:
        msgs.pop(0)


def build_session_messages(user_msg: str, system_prompt: str, session_id: str, max_history: int = 30) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    try:
        msgs = get_session(session_id)[-max_history:]
        for m in msgs:
            if m.get("role") in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        if len(messages) > max_history + 1:
            messages = [messages[0]] + messages[-(max_history):]
    except Exception:
        pass
    messages.append({"role": "user", "content": user_msg})
    return messages
