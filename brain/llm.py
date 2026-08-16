"""Fonctions LLM pour Alex Brain — opencode free models uniquement."""
import json
import asyncio
import re
from typing import Optional
import httpx

from .config import OPENCODE_API_URL, OPENCODE_MODEL
from .model_router import get_model_for_query, get_model_info

# Modèle actif (free par défaut)
_active_model = OPENCODE_MODEL

# Session persistante par modèle
_sessions: dict[str, str] = {}
_client: Optional[httpx.AsyncClient] = None

FREE_MODELS = [
    "deepseek-v4-flash-free",
    "mimo-v2.5-free",
    "nemotron-3-ultra-free",
    "longcat-2.0-free",
    "ling-3.0-tiny-free",
    "laguna-s-2.1-free",
    "north-mini-code-free",
]


def get_current_model():
    return _active_model


def set_current_model(model_id: str):
    global _active_model
    _active_model = model_id
    print(f"[brain] Modèle changé → {model_id}")


def _model_body(model_id: str = None):
    return {"modelID": model_id or _active_model, "providerID": "opencode"}


def _get_user_profile() -> str:
    """Récupère le profil utilisateur depuis la mémoire."""
    try:
        from . import memory
        facts = memory.get_all_facts()
        if not facts:
            return ""
        lines = []
        for f in facts:
            key = f.get("key", "")
            value = f.get("value", "")
            if key and value:
                lines.append(f"- {key}: {value}")
        if lines:
            return "Profil de l'utilisateur:\n" + "\n".join(lines)
    except Exception:
        pass
    return ""


def _build_message_with_profile(message: str, system_prompt: str = "") -> str:
    """Ajoute le profil utilisateur et le system prompt agent au message."""
    from .prompts import AGENT_LOOP_PROMPT
    prompt = system_prompt if system_prompt else AGENT_LOOP_PROMPT
    profile = _get_user_profile()
    parts = [prompt]
    if profile:
        parts.append(profile)
    parts.append(f"Message de l'utilisateur: {message}")
    return "\n\n".join(parts)


async def _get_client() -> httpx.AsyncClient:
    """Retourne un client HTTP persistant."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=120)
    return _client


async def _ensure_session(model_id: str) -> str:
    """Crée ou réutilise une session opencode persistante par modèle."""
    global _sessions
    client = await _get_client()

    if model_id in _sessions:
        return _sessions[model_id]

    resp = await client.post(
        f"{OPENCODE_API_URL}/session",
        json={"title": f"Alex-{model_id}"},
    )
    resp.raise_for_status()
    session_id = resp.json()["id"]
    _sessions[model_id] = session_id
    print(f"[brain] Nouvelle session pour {model_id}: {session_id}")
    return session_id


async def _collect_opencode_stream(message: str, system_prompt: str = ""):
    """Collecte tous les tokens puis sépare thinking de réponse."""
    # Router vers le bon modèle
    model_id = get_model_for_query(message)
    model_info = get_model_info(message)
    print(f"[brain] Routing: {model_info['task_type']} → {model_id} ({model_info['reason']})")

    full_message = _build_message_with_profile(message, system_prompt)
    client = await _get_client()
    session_id = await _ensure_session(model_id)

    # Envoyer le prompt
    resp = await client.post(
        f"{OPENCODE_API_URL}/session/{session_id}/prompt_async",
        json={
            "parts": [{"type": "text", "text": full_message}],
            "model": _model_body(model_id),
        },
    )
    if resp.status_code >= 400:
        return ("", "")

    # Écouter le SSE avec le MÊME client
    all_tokens = []
    req = client.build_request(
        "GET",
        f"{OPENCODE_API_URL}/event",
        headers={"Accept": "text/event-stream", "x-opencode-directory": "/home/jordy/alex-workspace"},
    )
    r = await client.send(req, stream=True)
    try:
        async for chunk in r.aiter_text():
            for line in chunk.split("\n"):
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                try:
                    evt = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                props = evt.get("properties", {})
                evt_type = evt.get("type", "")
                if props.get("sessionID") != session_id:
                    continue
                if evt_type == "message.part.delta":
                    field = props.get("field", "")
                    delta = props.get("delta", "")
                    if field == "text" and delta:
                        all_tokens.append(delta)
                elif evt_type == "message.updated":
                    info = props.get("info", {})
                    if info.get("role") == "assistant" and info.get("finish"):
                        break
                elif evt_type == "session.idle":
                    break
            else:
                continue
            break
    finally:
        await r.aclose()

    full = "".join(all_tokens)
    if not full.strip():
        return ("", "")

    import re
    # Parser les tags [PENSEE]...[/PENSEE] ou [PENSÉE]...[/PENSÉE]
    pensee_match = re.search(r'\[PENS[ÉE]E?\]([\s\S]*?)\[\/PENS[ÉE]E?\]', full, re.IGNORECASE)
    if pensee_match:
        thinking = pensee_match.group(1).strip()
        reply = full[pensee_match.end():].strip()
    else:
        # Pas de balise fermeture → prendre tout ce qui précède le premier texte visible
        pensee_start = re.search(r'\[PENS[ÉE]E?\]', full, re.IGNORECASE)
        if pensee_start:
            # Chercher la fin du bloc pensee (double newline après la balise)
            after_tag = full[pensee_start.end():]
            parts = after_tag.split('\n\n', 1)
            thinking = parts[0].strip()
            reply = parts[1].strip() if len(parts) > 1 else ""
        else:
            thinking = ""
            reply = full.strip()

    # Nettoyer les tags restants du reply
    reply = re.sub(r'\[PENS[ÉE]E?\]([\s\S]*?)\[\/PENS[ÉE]E?\]', '', reply, flags=re.IGNORECASE).strip()
    reply = re.sub(r'\[PENS[ÉE]E?\][\s\S]*$', '', reply, flags=re.IGNORECASE).strip()

    return (thinking, reply)


async def ask_opencode_stream(message: str, system_prompt: str = ""):
    """Async generator. Yield (text, is_final, is_thinking)."""
    try:
        thinking, reply = await _collect_opencode_stream(message, system_prompt)
        if thinking:
            yield (thinking, False, True)
        if reply:
            yield (reply, False, False)
        yield ("", True, False)
    except httpx.TimeoutException:
        yield ("", True, False)
    except Exception as e:
        print(f"[brain] opencode error: {e}")
        yield ("", True, False)


async def ask_opencode(message: str) -> Optional[str]:
    """Version non-streaming : collecte tous les tokens puis retourne la réponse complète."""
    reply_parts = []
    async for delta, is_final, is_thinking in ask_opencode_stream(message):
        if delta:
            reply_parts.append(delta)
        if is_final:
            break
    reply = "".join(reply_parts).strip()
    if reply:
        print(f"[brain] opencode reply ({len(reply)} chars)")
        return reply
    return None


async def reset_session():
    """Reset les sessions persistantes (utile en cas d'erreur)."""
    global _sessions
    _sessions = {}
    print("[brain] Sessions réinitialisées")
