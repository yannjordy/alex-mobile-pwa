import asyncio
import inspect
import json
import re
import time
import uuid
from typing import Any, Callable, Optional

from . import activity

_tools: dict[str, dict] = {}
_pending_actions: dict[str, dict] = {}
_cache: dict[str, tuple[float, str]] = {}
_CACHE_TTL = 300  # 5 minutes

def _cache_get(key: str) -> Optional[str]:
    entry = _cache.get(key)
    if entry and time.time() - entry[0] < _CACHE_TTL:
        return entry[1]
    if entry:
        del _cache[key]
    return None

def _cache_set(key: str, value: str) -> None:
    _cache[key] = (time.time(), value)
    if len(_cache) > 200:
        oldest = min(_cache.keys(), key=lambda k: _cache[k][0])
        del _cache[oldest]

def _cache_key(name: str, params: dict) -> str:
    return f"{name}:{json.dumps(params, sort_keys=True)}"


def _build_schema(func: Callable) -> dict:
    sig = inspect.signature(func)
    doc = inspect.getdoc(func) or ""
    props = {}
    required = []

    param_descs = {}
    in_args = False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith(("args:", "arguments:", "paramètres:", "params:")):
            in_args = True
            continue
        if in_args:
            if stripped == "" or not stripped[0].isalpha():
                in_args = False
                continue
            m = re.match(r'^(\w+)\s*[:\-]\s*(.+)', stripped)
            if m:
                param_descs[m.group(1)] = m.group(2)

    for name, param in sig.parameters.items():
        if name == "self":
            continue
        ptype = param.annotation if param.annotation is not inspect.Parameter.empty else str
        js_type = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }.get(ptype, "string")
        prop = {"type": js_type}
        if name in param_descs:
            prop["description"] = param_descs[name]
        if param.default is not inspect.Parameter.empty:
            prop["default"] = param.default
        else:
            required.append(name)
        props[name] = prop
    return {
        "type": "object",
        "properties": props,
        "required": required,
    }


def tool(name: str, description: str, dangerous: bool = False):
    def decorator(func: Callable):
        _tools[name] = {
            "func": func,
            "name": name,
            "description": description,
            "parameters": _build_schema(func),
            "dangerous": dangerous,
        }
        return func
    return decorator


def list_tools() -> list[dict]:
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["parameters"],
            "dangerous": t["dangerous"],
            "skill": t.get("skill", "core"),
        }
        for t in _tools.values()
    ]


def list_tools_openai() -> list[dict]:
    result = []
    for t in _tools.values():
        openai_tool = {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        result.append(openai_tool)
    return result


_CACHEABLE_TOOLS: set[str] = {"recherche_web", "recherche_image", "recherche_video", "recherche_audio", "recherche_fichier", "meteo", "info_systeme"}

async def execute(name: str, params: dict, force: bool = False) -> str:
    t = _tools.get(name)
    if not t:
        activity.log("warn", f"Outil inconnu demandé : {name}")
        return f"Outil « {name} » inconnu."
    
    # Si l'outil est dangereux et pas forcé, créer une action en attente
    if t["dangerous"] and not force:
        cid = create_pending(name, name, params, "")
        activity.log("warn", f"Outil dangereux en attente de confirmation : {name} (cid={cid})")
        return f"⚠️ Action dangereuse nécessitant confirmation. ID: {cid}"
    
    ck = _cache_key(name, params)
    if name in _CACHEABLE_TOOLS:
        cached = _cache_get(ck)
        if cached is not None:
            return cached
    _log_params = dict(params or {})
    for k, v in list(_log_params.items()):
        if isinstance(v, str) and len(v) > 120:
            _log_params[k] = v[:120] + "…"
    activity.log("cmd", f"{name} {json.dumps(_log_params, ensure_ascii=False)}", source="tools")
    try:
        func = t["func"]
        if asyncio.iscoroutinefunction(func):
            result = await func(**params)
        else:
            result = func(**params)
        if name in _CACHEABLE_TOOLS:
            _cache_set(ck, result)
        activity.log("success", f"{name} → terminé")
        return result
    except Exception as e:
        activity.log("error", f"{name} → {e}")
        return f"Erreur lors de l'exécution de « {name} » : {e}"


def create_pending(action: str, tool_name: str, params: dict, user_message: str) -> str:
    cid = uuid.uuid4().hex[:12]
    _pending_actions[cid] = {
        "tool": tool_name,
        "params": params,
        "action": action,
        "user_message": user_message,
    }
    return cid


def get_pending(cid: str) -> Optional[dict]:
    return _pending_actions.get(cid)


def remove_pending(cid: str):
    _pending_actions.pop(cid, None)


def get_tool_info(name: str) -> Optional[dict]:
    return _tools.get(name)


# Register orb tool
from .orb import set_shape as _set_shape, SHAPES as _SHAPES
_tools["set_shape"] = {
    "func": _set_shape,
    "name": "set_shape",
    "description": "Change la forme de l'orb Alex. Utilise cette forme pour illustrer visuellement le contexte.",
    "parameters": {
        "type": "object",
        "properties": {
            "shape": {"type": "string", "description": f"Nom de la forme. Disponibles : {', '.join(_SHAPES)}"},
            "hold_ms": {"type": "integer", "description": "Durée d'affichage en ms", "default": 5000},
        },
        "required": ["shape"],
    },
    "dangerous": False,
}
