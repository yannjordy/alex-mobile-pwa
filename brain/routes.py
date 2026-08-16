"""Routes API pour Alex Brain."""
import asyncio
import json
import os
import time
import logging
import re
import random
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse

from pydantic import BaseModel

from . import wake_word
from . import tools as tools_registry
from . import memory
from .skills.manager import skill_manager
from .tools import selfprogramming as _tools_selfprogramming
from .tools import downloads as _tools_downloads
from .tools import activity as _tools_activity
from .tools import position as _tools_position
from .tools import map as _tools_map
from .tools import automation as _tools_automation
from .tools import system as _tools_system
from .tools import weather as _tools_weather
from .tools import network as _tools_network
from .tools import desktop as _tools_desktop
from .tools import devices as _tools_devices
from .tools import files as _tools_files
from .tools import security as _tools_security
from .tools import scheduler as _tools_scheduler
from .tools import web as _tools_web
from .tools import website as _tools_website
from .tools import workflow as _tools_workflow
from .tools import mcp as _tools_mcp
from .integrations import tools as _tools_integrations
from . import proactive
from . import llm
from . import session
from .prompts import (
    SYSTEM_PROMPT, COMPACT_SYSTEM_PROMPT, AGENT_LOOP_PROMPT,
    TOOL_PROMPT, ESSENTIAL_TOOLS, AUTONOMOUS_TOOLS,
)
from .config import USER_NAME, API_KEY

logger = logging.getLogger("alex.routes")

# Auto-shape : détecte les mots-clés et suggère une forme
_SHAPE_KEYWORDS = {
    "heure|temps|clock|horloge|minuit|midi": "clock",
    "musique|chanson|écoute|spotify|album|rythme": "music",
    "code|script|fonction|programme|debug|git|github": "code",
    "météo|pluie|soleil|température|degrés|nuage": "cloud",
    "photo|image|caméra|selfie|capture": "camera",
    "erreur|bug|échec|planté|crash": "error",
    "sécurité|mot de passe|verrouiller|protéger|lock": "shield",
    "idée|conseil|astuce|lightbulb|proposition": "lightbulb",
    "recherche|chercher|google|trouver|query": "search",
    "téléphone|appel|mobile|sms": "phone",
    "fichier|dossier|télécharger|upload|download": "folder",
    "rapide|vite|flash|lightning|accelere": "lightning",
    "amour|❤|coeur|heart|couple": "heart",
    "étoile|star|favori|note": "star",
    "code|terminal|console|commande": "terminal",
    "carte|map|gps|lieu|adresse": "map",
    "cloche|notification|rappel|alerte": "bell",
    "nuage|cloud|stockage|serveur": "cloud",
    "rouage|config|réglage|paramètre|option": "gear",
    "bogue|insecte|bug|ver": "bug",
    "clé|key|accès|auth|token": "key",
    "bouclier|defend|protect|sécurise": "shield",
    "fusée|rocket|lancement|départ|start": "rocket",
    "cerveau|intelligence|pense|réfléchis|brain": "brain",
    "œil|eye|voir|regarde|visualise": "eye",
    "feu|fire|brûle|chaud|flamme": "fire",
    "éclat|sparkle|magique|brille|etincelle": "sparkles",
    "montagne|户外|nature|randonnée": "mountain",
    "bateau|mer|océan|voyage": "boat",
    "monde|globe|international|pays": "globe",
    "graphique|stats|données|chart|mesure": "chart",
    "boussole|compass|direction|orient": "compass",
    "télé|tv|stream|regarder|écran": "tv",
    "heure|clock|minuit|midi|matin|soir": "clock",
    "heure|heure|time": "clock",
    "heure|heure actuelle|il est": "clock",
}


def _detect_auto_shape(text: str) -> str | None:
    """Détecte un shape basé sur les mots-clés du texte (pas de match si trop court)."""
    if len(text) < 20:
        return None
    lower = text.lower()
    for pattern, shape in _SHAPE_KEYWORDS.items():
        for kw in pattern.split("|"):
            if kw in lower:
                return shape
    return None


app = FastAPI(title="Alex Brain")

# CORS sécurisé : origins configurables via variable d'environnement
_ALEX_CORS_ORIGINS = os.environ.get("ALEX_CORS_ORIGINS", "http://localhost:8765,http://127.0.0.1:8765").split(",")
app.add_middleware(
    __import__('fastapi.middleware.cors', fromlist=['CORSMiddleware']).CORSMiddleware,
    allow_origins=_ALEX_CORS_ORIGINS,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Middleware d'authentification API
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse as StarletteJSONResponse

# Routes qui ne nécessitent pas d'authentification
_PUBLIC_PATHS = {"/", "/health", "/ready", "/manifest.json", "/service-worker.js"}

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Pas d'auth si pas de clé configurée
        if not API_KEY:
            return await call_next(request)
        
        # Routes publiques exemptées
        path = request.url.path
        if path in _PUBLIC_PATHS or path.startswith("/static") or path.endswith((".js", ".css", ".html", ".ico", ".png", ".svg", ".woff2")):
            return await call_next(request)
        
        # Vérifier le header Authorization
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "") if auth.startswith("Bearer ") else ""
        
        if token != API_KEY:
            return StarletteJSONResponse(
                {"error": "Non autorisé. Header Authorization: Bearer <API_KEY> requis."},
                status_code=401
            )
        
        return await call_next(request)

app.add_middleware(AuthMiddleware)

# ─── Static file serving (for running without Electron) ──────────────────────
ALEX_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_connected_websockets: list[WebSocket] = []
_main_loop: Optional[asyncio.AbstractEventLoop] = None
_network_connected: bool = False
_last_network_check: float = 0
_latest_screen_image: Optional[str] = None


class ChatRequest(BaseModel):
    message: str
    mode: str = "auto"
    session_id: str = ""
    forme: str = "sphère"
    cid: str = ""
    system_prompt: str = ""


class ShapeRequest(BaseModel):
    shape: str = ""
    hold_ms: int = 5000
    style: str = ""


class ChatResponse(BaseModel):
    reply: str
    source: str


class ModelChangeRequest(BaseModel):
    model: str


class VisionRequest(BaseModel):
    image: str


class VisionAskRequest(BaseModel):
    question: str = "Décris ce que tu vois sur l'écran en français."


class ImageAnalysisRequest(BaseModel):
    image: str
    question: str = "Décris cette image en français."


class DocumentAnalysisRequest(BaseModel):
    content: str
    filename: str
    question: str = "Résume ce document en français."


class ToolExecRequest(BaseModel):
    tool: str
    params: dict = {}


class ToolConfirmRequest(BaseModel):
    confirmation_id: str
    accept: bool = True


class DownloadCancelRequest(BaseModel):
    id: str


class MemoryLearnRequest(BaseModel):
    key: str
    value: str
    category: str = "general"


class CodeEventRequest(BaseModel):
    path: str = ""
    code: str = ""
    lang: str = ""


class CodeRunRequest(BaseModel):
    path: str = ""
    code: str = ""
    lang: str = "js"


class PositionUpdate(BaseModel):
    cursor: Optional[dict] = None
    window: Optional[dict] = None


class MapDataRequest(BaseModel):
    markers: Optional[list] = None
    routes: Optional[list] = None
    legends: Optional[list] = None


_tool_descriptions = None


async def _check_network() -> bool:
    global _network_connected, _last_network_check
    now = time.time()
    if now - _last_network_check < 15:
        return _network_connected
    _last_network_check = now
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5, verify=False) as c:
            await c.get("https://www.google.com/generate_204")
        _network_connected = True
    except Exception:
        _network_connected = False
    return _network_connected


async def _broadcast_wake():
    dead = []
    for ws in _connected_websockets:
        try:
            await ws.send_json({"event": "wake"})
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connected_websockets.remove(ws)


async def _broadcast_event(event: str, payload: dict):
    dead = []
    data = {"event": event, **payload}
    for ws in _connected_websockets:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _connected_websockets.remove(ws)


def _push_notification(title: str, message: str):
    try:
        _tools_automation._notify(title, message)
    except Exception:
        pass
    if _main_loop is not None:
        asyncio.run_coroutine_threadsafe(
            _broadcast_event("notification", {"title": title, "message": message}),
            _main_loop,
        )


def _on_wake_from_thread():
    if _main_loop is not None:
        asyncio.run_coroutine_threadsafe(_broadcast_wake(), _main_loop)


def _on_code_changed(path: str, diff: str, ok: bool, old: str = None, new: str = None, lang: str = None):
    if _main_loop is not None:
        asyncio.run_coroutine_threadsafe(
            _broadcast_event("code_changed", {
                "path": path, "diff": diff, "ok": ok,
                "old": old, "new": new, "lang": lang,
                "time": time.time(),
            }),
            _main_loop,
        )


def _save_interaction(user_msg: str, assistant_reply: str):
    try:
        memory.save_conversation("user", user_msg)
        memory.save_conversation("assistant", assistant_reply)
        _extract_user_data(user_msg)
    except Exception as e:
        logger.error("Erreur sauvegarde interaction: %s", e)


def _extract_user_data(message: str):
    """Extrait et sauvegarde les données utilisateur pertinentes."""
    import re
    msg_lower = message.lower()

    patterns = {
        "nom": [
            r"(?:je m'appelle|mon nom est|je suis|appelle[- ]moi)\s+(\w+)",
            r"mon prénom est\s+(\w+)",
        ],
        "email": [
            r"[\w.-]+@[\w.-]+\.\w+",
        ],
        "ville": [
            r"j'habite à\s+(\w[\w\s]*?)(?:\.|,|$)",
            r"je vis à\s+(\w[\w\s]*?)(?:\.|,|$)",
        ],
        "age": [
            r"j'ai\s+(\d+)\s+ans",
            r"mon âge est\s+(\d+)",
        ],
        "travail": [
            r"je suis\s+(\w[\w\s]*?)(?:\.|,|$)",
            r"je travaille (?:en tant que|comme|chez)\s+(.+?)(?:\.|,|$)",
        ],
        "loisirs": [
            r"j'aime\s+(.+?)(?:\.|,|$)",
            r"mes hobbies sont\s+(.+?)(?:\.|,|$)",
            r"je fais du\s+(\w+)",
        ],
    }

    for key, pats in patterns.items():
        for pat in pats:
            match = re.search(pat, msg_lower)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                if len(value) > 2 and len(value) < 100:
                    memory.save_fact(f"user_{key}", value, category="user_profile")
                    print(f"[brain] Donnée utilisateur sauvegardée: {key}={value}")
                    break


def _get_tool_prompt(essential_only: bool = False) -> str:
    global _tool_descriptions
    if essential_only:
        lines = []
        for t in tools_registry.list_tools():
            if t["name"] in ESSENTIAL_TOOLS:
                marker = " ⚠️ confirmation requise" if t["dangerous"] else ""
                lines.append(f"  - {t['name']}: {t['description']}{marker}")
        return TOOL_PROMPT + "\n".join(lines)
    if _tool_descriptions is None:
        lines = []
        for t in tools_registry.list_tools():
            marker = " ⚠️ confirmation requise" if t["dangerous"] else ""
            lines.append(f"  - {t['name']}: {t['description']}{marker}")
        _tool_descriptions = TOOL_PROMPT + "\n".join(lines)
    return _tool_descriptions


def _build_agent_loop_prompt() -> str:
    parts = [AGENT_LOOP_PROMPT]
    try:
        facts = memory.get_all_facts()
        if facts:
            lines = "\n".join(f"  - {f['key']}: {f['value']}" for f in facts[:15])
            parts.append(f"## Ce que je sais sur {USER_NAME}\n{lines}")
        level_info = memory.get_level()
        parts.append(f"## Mon expérience\nNiveau {level_info['level']}, {level_info['total_interactions']} interactions à vie.")
    except Exception:
        pass
    return "\n\n".join(parts)


def _build_system_prompt(with_memory: bool = True) -> str:
    base = SYSTEM_PROMPT
    if not with_memory:
        return base
    try:
        facts = memory.get_all_facts()
        if facts:
            lines = "\n".join(f"  - {f['key']}: {f['value']}" for f in facts[:15])
            base += f"\n\n## Ce que je sais sur {USER_NAME}\n{lines}"
        level_info = memory.get_level()
        base += f"\n\n## Mon expérience\nNiveau {level_info['level']}, {level_info['total_interactions']} interactions à vie."
    except Exception:
        pass
    return base


def _build_compact_system_prompt() -> str:
    base = COMPACT_SYSTEM_PROMPT
    try:
        facts = memory.get_all_facts()
        if facts:
            lines = "\n".join(f"  - {f['key']}: {f['value']}" for f in facts[:15])
            base += f"\n\n## Ce que je sais sur {USER_NAME}\n{lines}"
        level_info = memory.get_level()
        base += f"\n\n## Mon expérience\nNiveau {level_info['level']}, {level_info['total_interactions']} interactions à vie."
    except Exception:
        pass
    return base


def _parse_tool_calls(text: str) -> list[dict]:
    """Extrait les appels d'outils [[tool:nom:param=valeur,...]] du texte."""
    import re
    from .tools import _tools as registered_tools
    pattern = r'\[\[tool:([a-zA-Z_]+)(?::([^\]]*))?\]\]'
    calls = []
    for match in re.finditer(pattern, text):
        tool_name = match.group(1)
        args_str = match.group(2) or ""
        params = {}
        if args_str:
            for part in args_str.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip()] = v.strip()
        # Ignorer les examples (tool "nom" n'existe pas)
        if tool_name not in registered_tools:
            continue
        calls.append({"tool": tool_name, "params": params, "raw": match.group(0)})
    return calls


def _replace_tool_calls(text: str, results: dict[str, str]) -> str:
    """Remplace les [[tool:...]] par les résultats d'exécution."""
    import re
    from .tools import _tools as registered_tools
    pattern = r'\[\[tool:([a-zA-Z_]+)(?::([^\]]*))?\]\]'
    def replacer(match):
        tool_name = match.group(1)
        if tool_name not in registered_tools:
            return match.group(0)  # garder les examples intacts
        args_str = match.group(2) or ""
        key = f"{tool_name}:{args_str}"
        return results.get(key, f"[outil {tool_name} non exécuté]")
    return re.sub(pattern, replacer, text)


async def _agent_loop(user_message: str, session_id: str = "") -> Optional[str]:
    """Agent loop : tout passe par le LLM opencode, puis exécution des tools."""
    reply = await llm.ask_opencode(user_message)
    if not reply:
        return "Modèle indisponible. Vérifie qu'opencode tourne."

    tool_calls = _parse_tool_calls(reply)
    if not tool_calls:
        _save_interaction(user_message, reply[:300])
        return reply

    results = {}
    for tc in tool_calls:
        tool_name = tc["tool"]
        params = tc["params"]
        try:
            result = await tools_registry.execute(tool_name, params)
            # Si c'est une action en attente de confirmation
            if result.startswith("⚠️ Action dangereuse"):
                results[f"{tool_name}:{':'.join(f'{k}={v}' for k,v in params.items())}"] = result
            else:
                results[f"{tool_name}:{':'.join(f'{k}={v}' for k,v in params.items())}"] = str(result)
            print(f"[brain] Tool exécuté: {tool_name} → {str(result)[:100]}")
        except Exception as e:
            results[f"{tool_name}:{':'.join(f'{k}={v}' for k,v in params.items())}"] = f"Erreur: {e}"
            print(f"[brain] Tool erreur: {tool_name} → {e}")

    final_reply = _replace_tool_calls(reply, results)
    _save_interaction(user_message, final_reply[:300])
    return final_reply


async def _agent_loop_stream(user_message: str):
    """Agent loop streaming : yield les tokens au fur et à mesure."""
    full_reply = []
    async for delta, is_final in llm.ask_opencode_stream(user_message):
        if delta:
            full_reply.append(delta)
            yield delta
        if is_final:
            break
    reply_text = "".join(full_reply).strip()
    if reply_text:
        _save_interaction(user_message, reply_text[:300])


async def _alarm_scheduler():
    while True:
        try:
            fired = _tools_automation.check_due_alarms()
            if fired:
                for a in fired:
                    label = a.get('label', 'Réveil')
                    now = datetime.now()
                    hour = now.hour
                    
                    # Messages intelligents selon l'heure
                    if 5 <= hour < 9:
                        greetings = [
                            "Bon matin ! ☀️ Lever de soleil, réveille-toi !",
                            "Bonjour ! Une belle journée t'attend !",
                            "Salut ! Il est temps de se lever !",
                        ]
                    elif 9 <= hour < 12:
                        greetings = [
                            "Bonjour ! Déjà en retard ? 😄",
                            "Hey ! Tu dormais encore ?",
                        ]
                    elif 12 <= hour < 14:
                        greetings = [
                            "Midi ! Pause déjeuner !",
                            "Il est midi, time to eat !",
                        ]
                    elif 14 <= hour < 18:
                        greetings = [
                            "Après-midi ! Tu avais quelque chose à faire.",
                            "Hey, tu avais prévu quelque chose.",
                        ]
                    else:
                        greetings = [
                            "Bonsoir ! Il est temps de se coucher.",
                            "Dodo ! Demain c'est un autre jour.",
                        ]
                    
                    import random
                    greeting = random.choice(greetings)
                    
                    _push_notification(
                        "Alex ⏰",
                        f"{greeting}\n{label}",
                    )
                    print(f"[brain] Alarme déclenchée : {label} à {a.get('time')}")
        except Exception as e:
            print(f"[brain] Erreur alarme scheduler: {e}")
        await asyncio.sleep(15)


@app.on_event("startup")
async def on_startup():
    global _main_loop
    _main_loop = asyncio.get_event_loop()
    wake_word.on_wake(_on_wake_from_thread)
    wake_word.start_background()
    asyncio.create_task(_alarm_scheduler())

    from . import security_monitor
    asyncio.create_task(security_monitor.security_check_loop(_broadcast_event))

    proactive.init(_broadcast_event, _push_notification)
    # asyncio.create_task(proactive.proactive_loop())  # Désactivé : pas de messages automatiques

    _tools_selfprogramming.set_code_listener(_on_code_changed)

    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    found = skill_manager.discover(skills_dir)
    for name in found:
        try:
            ok = skill_manager.load(name, [skills_dir])
            if ok:
                s = skill_manager.skills.get(name)
                print(f"[skills] Chargé : {s.name if s else name}")
        except Exception as e:
            print(f"[skills] Erreur chargement {name}: {e}")
    print(f"[skills] {len(skill_manager.skills)} skill(s) actif(s)")


@app.on_event("shutdown")
async def on_shutdown():
    pass


@app.websocket("/wake")
async def wake_socket(websocket: WebSocket):
    await websocket.accept()
    _connected_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in _connected_websockets:
            _connected_websockets.remove(websocket)


@app.get("/health")
async def health():
    online = await _check_network()
    return {"status": "ok", "model": llm.get_current_model(), "online": online}


@app.get("/ready")
async def ready():
    return {"ready": True}


@app.post("/position/update")
async def position_update(req: PositionUpdate):
    _tools_position.update_from_frontend(cursor=req.cursor, window=req.window)
    return {"status": "ok"}


@app.get("/map/data")
async def map_data():
    return _tools_map.get_data()


@app.post("/map/data")
async def map_data_save(req: MapDataRequest):
    data = {"markers": req.markers or [], "routes": req.routes or [], "legends": req.legends or []}
    try:
        _tools_map.save_data(data)
        return {"status": "ok"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/code/log")
async def code_log(limit: int = 30):
    log = _tools_selfprogramming.get_code_log(limit)
    return {"events": log}


@app.post("/code/event")
async def code_event(req: CodeEventRequest):
    ev = _tools_selfprogramming.record_chat_code(req.path or "code.txt", req.code or "", req.lang or "")
    return {"status": "ok", "event": ev}


@app.get("/code/file")
async def code_file(path: str):
    full = _tools_selfprogramming.ALEX_ROOT / path
    if not full.exists():
        hits = list(_tools_selfprogramming.ALEX_ROOT.rglob(path))
        full = hits[0] if hits else None
    if full is None:
        return JSONResponse({"error": "introuvable"}, status_code=404)
    try:
        content = full.read_text(encoding="utf-8")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    return {"path": path, "content": content}


@app.post("/code/run")
async def code_run(req: CodeRunRequest):
    import subprocess, tempfile, sys
    code = req.code or ""
    lang = req.lang or ""
    if not code and req.path:
        try:
            full = _tools_selfprogramming.ALEX_ROOT / req.path
            if not full.exists():
                hits = list(_tools_selfprogramming.ALEX_ROOT.rglob(req.path))
                full = hits[0] if hits else None
            if full is None:
                return JSONResponse({"error": "Fichier introuvable", "output": ""}, status_code=404)
            code = full.read_text(encoding="utf-8")
            lang = lang or _tools_selfprogramming._lang_from_path(req.path)
        except Exception as e:
            return JSONResponse({"error": str(e), "output": ""}, status_code=500)

    ext_map = {"javascript": ".js", "js": ".js", "node": ".js", "python": ".py", "py": ".py"}
    ext = ext_map.get(lang, ".js")
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False, mode="w", encoding="utf-8") as tf:
        tf.write(code)
        tmp_path = tf.name
    try:
        if ext == ".py":
            cmd = [sys.executable, tmp_path]
        else:
            cmd = ["node", tmp_path]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15, cwd=str(_tools_selfprogramming.ALEX_ROOT))
        return {
            "ok": proc.returncode == 0,
            "output": proc.stdout[:4000] + (("\n" + proc.stderr[:4000]) if proc.stderr.strip() else ""),
            "returncode": proc.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "⏱️ Dépassement du délai d'exécution (15 s).", "returncode": None}
    except Exception as e:
        return {"ok": False, "output": f"Erreur exécution : {e}", "returncode": None}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.get("/code/serve")
async def code_serve(path: str):
    import mimetypes
    full = _tools_selfprogramming.ALEX_ROOT / path
    if not full.exists():
        hits = list(_tools_selfprogramming.ALEX_ROOT.rglob(path))
        full = hits[0] if hits else None
    if full is None:
        return JSONResponse({"error": "introuvable"}, status_code=404)
    try:
        media_type = mimetypes.guess_type(str(full))[0] or "text/plain"
        return FileResponse(full, media_type=media_type)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/vision/analyze")
async def vision_analyze(req: VisionRequest):
    global _latest_screen_image
    _latest_screen_image = req.image
    return {"status": "received"}


@app.get("/vision/latest")
async def vision_latest():
    if _latest_screen_image:
        return {"image": _latest_screen_image[:100] + "..."}
    return {"image": None}


@app.post("/vision/ask")
async def vision_ask(req: VisionAskRequest):
    global _latest_screen_image
    if not _latest_screen_image:
        return {"reply": "Je n'ai pas d'image d'écran en mémoire. Active d'abord le partage d'écran depuis l'orb du bureau."}

    if ANTHROPIC_API_KEY:
        try:
            import base64
            import httpx
            image_data = _latest_screen_image.split(",")[1] if "," in _latest_screen_image else _latest_screen_image
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": ANTHROPIC_MODEL,
                        "max_tokens": 500,
                        "system": f"Tu es Alex. Tu observes l'écran de {USER_NAME}. Réponds en français de façon concise et utile.",
                        "messages": [{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": req.question},
                                {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_data}}
                            ]
                        }],
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
                text = "\n".join(parts).strip()
                return {"reply": text or "Je ne vois rien de particulier."}
        except Exception as e:
            return {"reply": f"Je n'ai pas pu analyser l'écran : {str(e)}"}

    return {"reply": "Je ne peux pas analyser l'écran pour le moment — aucune API vision (Anthropic) configurée."}


@app.post("/vision/stop")
async def vision_stop():
    global _latest_screen_image
    _latest_screen_image = None
    return {"status": "stopped"}


@app.post("/vision/analyze-image")
async def analyze_user_image(req: ImageAnalysisRequest):
    """Analyse une image envoyée par l'utilisateur via opencode free models."""
    from .llm import ask_opencode, _model_body, _ensure_session, _get_client
    from .config import OPENCODE_API_URL

    try:
        prompt = f"Tu es Alex, l'assistante de {USER_NAME}. Tu analyses les images qu'on t'envoie. Réponds en français, sois concise et utile.\n\nImage en base64 (format data URL) :\n{req.image}\n\nQuestion : {req.question}"

        client = await _get_client()
        session_id = await _ensure_session("mimo-v2.5-free")

        resp = await client.post(
            f"{OPENCODE_API_URL}/session/{session_id}/prompt_async",
            json={
                "parts": [{"type": "text", "text": prompt}],
                "model": _model_body("mimo-v2.5-free"),
            },
        )
        if resp.status_code >= 400:
            return {"reply": "Je n'ai pas pu analyser l'image — erreur serveur."}

        all_tokens = []
        req_evt = client.build_request(
            "GET",
            f"{OPENCODE_API_URL}/event",
            headers={"Accept": "text/event-stream", "x-opencode-directory": "/home/jordy/alex-workspace"},
        )
        r = await client.send(req_evt, stream=True)
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

        reply = "".join(all_tokens).strip()
        return {"reply": reply or "Je ne vois rien de particulier dans cette image."}
    except Exception as e:
        return {"reply": f"Je n'ai pas pu analyser l'image : {str(e)}"}


@app.post("/vision/analyze-document")
async def analyze_user_document(req: DocumentAnalysisRequest):
    """Analyse un document envoyé par l'utilisateur via opencode free models."""
    from .llm import _model_body, _ensure_session, _get_client
    from .config import OPENCODE_API_URL

    try:
        prompt = f"Tu es Alex, l'assistante de {USER_NAME}. Tu analyses les documents qu'on t'envoie. Réponds en français, sois concise et utile.\n\nContenu du document « {req.filename} » :\n{req.content}\n\nQuestion : {req.question}"

        client = await _get_client()
        session_id = await _ensure_session("mimo-v2.5-free")

        resp = await client.post(
            f"{OPENCODE_API_URL}/session/{session_id}/prompt_async",
            json={
                "parts": [{"type": "text", "text": prompt}],
                "model": _model_body("mimo-v2.5-free"),
            },
        )
        if resp.status_code >= 400:
            return {"reply": "Je n'ai pas pu analyser le document — erreur serveur."}

        all_tokens = []
        req_evt = client.build_request(
            "GET",
            f"{OPENCODE_API_URL}/event",
            headers={"Accept": "text/event-stream", "x-opencode-directory": "/home/jordy/alex-workspace"},
        )
        r = await client.send(req_evt, stream=True)
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

        reply = "".join(all_tokens).strip()
        return {"reply": reply or "Je n'ai pas pu lire le contenu de ce document."}
    except Exception as e:
        return {"reply": f"Je n'ai pas pu analyser le document : {str(e)}"}


@app.get("/tools")
async def list_tools():
    return {"tools": tools_registry.list_tools()}


@app.get("/memory")
async def get_memory():
    try:
        facts = memory.get_all_facts()
        level = memory.get_level()
        today = memory.get_today_learning()
        recent = memory.get_recent_conversations(10)
        return {
            "level": level,
            "facts_count": len(facts),
            "today": today,
            "recent": [{"role": c["role"], "content": c["content"][:80]} for c in recent[:5]],
        }
    except Exception as e:
        return {"error": str(e)}


@app.post("/memory/learn")
async def memory_learn(req: MemoryLearnRequest):
    try:
        memory.save_fact(req.key, req.value, req.category)
        memory.record_learning(f"Appris : {req.key} = {req.value}", [req.category])
        return {"status": "learned"}
    except Exception as e:
        return {"error": str(e)}


@app.get("/memory/facts")
async def memory_facts():
    try:
        return {"facts": memory.get_all_facts()}
    except Exception as e:
        return {"error": str(e)}


@app.get("/history")
async def get_history(limit: int = 300):
    try:
        convs = memory.get_recent_conversations(limit)
        msgs = [
            {"role": c["role"], "content": c["content"], "created_at": c.get("created_at", ""), "id": c.get("id")}
            for c in convs
        ]
        return {"messages": msgs}
    except Exception as e:
        return {"messages": [], "error": str(e)}


@app.delete("/history")
async def clear_history():
    try:
        memory.clear_conversations()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.delete("/history/range")
async def delete_history_range(start: int, end: int):
    try:
        memory.delete_conversation_range(start, end)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/tools/execute")
async def execute_tool(req: ToolExecRequest):
    result = await tools_registry.execute(req.tool, req.params)
    return {"result": result, "source": "tool"}


@app.post("/tools/confirm")
async def confirm_tool(req: ToolConfirmRequest):
    pending = tools_registry.get_pending(req.confirmation_id)
    if not pending:
        return {"success": False, "error": "Action confirmée expirée ou introuvable."}
    if not req.accept:
        tools_registry.remove_pending(req.confirmation_id)
        return {"success": True, "result": "Action annulée.", "source": "tool"}
    result = await tools_registry.execute(pending["tool"], pending["params"], force=True)
    tools_registry.remove_pending(req.confirmation_id)
    return {"success": True, "result": result, "source": "tool"}


@app.get("/downloads/status")
async def downloads_status():
    return {
        "items": _tools_downloads.manager.snapshot(),
        "active": _tools_downloads.manager.active_count(),
    }


@app.post("/downloads/cancel")
async def downloads_cancel(req: DownloadCancelRequest):
    ok = _tools_downloads.manager.kill(req.id)
    return {"success": ok}


@app.get("/activity")
async def activity_status(limit: int = 120):
    events = _tools_activity.snapshot(limit)
    return {"events": events}


@app.post("/activity/clear")
async def activity_clear():
    _tools_activity.clear()
    return {"status": "ok"}


@app.get("/skills")
async def list_skills():
    return {"skills": skill_manager.list_skills()}


@app.post("/skills/{name}/load")
async def load_skill(name: str):
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    ok = skill_manager.load(name, [skills_dir])
    return {"success": ok}


@app.post("/skills/{name}/unload")
async def unload_skill(name: str):
    ok = skill_manager.unload(name)
    return {"success": ok}


@app.post("/skills/{name}/reload")
async def reload_skill(name: str):
    skills_dir = os.path.join(os.path.dirname(__file__), "skills")
    ok = skill_manager.reload(name, [skills_dir])
    return {"success": ok}


@app.post("/shape")
async def set_shape(req: ShapeRequest):
    """Change la forme de l'orb Alex via le frontend WebSocket."""
    shape_data = {"shape": req.shape, "hold_ms": req.hold_ms}
    if req.style:
        shape_data["style"] = req.style
    await _broadcast_event("shape_change", shape_data)
    return {"status": "ok", "shape": req.shape}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    reply = await _agent_loop(req.message, req.session_id)
    if reply:
        return ChatResponse(reply=reply, source="opencode")
    return ChatResponse(reply="Modèle indisponible.", source="none")


@app.post("/chat/opencode")
async def chat_opencode(req: ChatRequest):
    """Endpoint streaming SSE : thinking + delta + exécution des tools."""

    async def generate():
        print(f"[brain] opencode chat: {req.message[:50]}")
        full_reply = []
        async for delta, is_final, is_thinking in llm.ask_opencode_stream(req.message, req.system_prompt):
            if delta:
                if is_thinking:
                    yield f"data: {json.dumps({'type': 'thinking', 'text': delta})}\n\n"
                else:
                    full_reply.append(delta)
                    yield f"data: {json.dumps({'type': 'delta', 'text': delta})}\n\n"
            if is_final:
                break

        reply_text = "".join(full_reply).strip()

        # Parse [FORME:xxx] tags → envoyer shape_change via SSE
        import re as _re
        forme_matches = _re.findall(r'\[FORME:(\w+)\]', reply_text)
        for forme in forme_matches:
            yield f"data: {json.dumps({'shape': forme})}\n\n"
        reply_text = _re.sub(r'\[FORME:\w+\]', '', reply_text).strip()

        # Auto-shape detection si pas de [FORME:] explicite
        if not forme_matches and reply_text:
            auto_shape = _detect_auto_shape(reply_text)
            if auto_shape:
                yield f"data: {json.dumps({'shape': auto_shape})}\n\n"

        tool_calls = _parse_tool_calls(reply_text) if reply_text else []

        if tool_calls:
            results = {}
            for tc in tool_calls:
                tool_name = tc["tool"]
                params = tc["params"]
                try:
                    result = await tools_registry.execute(tool_name, params)
                    key = f"{tool_name}:{':'.join(f'{k}={v}' for k,v in params.items())}"
                    if result.startswith("⚠️ Action dangereuse"):
                        results[key] = result
                    else:
                        results[key] = str(result)
                    print(f"[brain] Tool SSE exécuté: {tool_name}")
                except Exception as e:
                    key = f"{tool_name}:{':'.join(f'{k}={v}' for k,v in params.items())}"
                    results[key] = f"Erreur: {e}"

            final_reply = _replace_tool_calls(reply_text, results)
            remaining = final_reply[len(reply_text):]
            if remaining:
                yield f"data: {json.dumps({'type': 'delta', 'text': remaining})}\n\n"

            _save_interaction(req.message, final_reply[:300])
        elif reply_text:
            _save_interaction(req.message, reply_text[:300])

        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """Endpoint streaming : thinking séparé de la réponse."""

    async def generate():
        async for delta, is_final, is_thinking in llm.ask_opencode_stream(req.message):
            if delta:
                if is_thinking:
                    yield f"data: {json.dumps({'type': 'thinking', 'text': delta})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'delta', 'text': delta})}\n\n"
            if is_final:
                break
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/voices")
async def list_voices():
    """Liste les voix TTS disponibles."""
    from .vocal import list_voices as _list_voices
    return {"voices": _list_voices()}


class VocalRequest(BaseModel):
    text: str
    voice: str = "denise"


@app.post("/vocal")
async def vocal_tts(req: VocalRequest):
    """Génère un audio MP3 à partir du texte (Edge TTS)."""
    from .vocal import tts_generate
    try:
        audio = await tts_generate(req.text, req.voice)
        return StreamingResponse(
            iter([audio]),
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=tts.mp3"}
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/stt")
async def stt_transcribe(request: Request):
    """Transcrit un audio en texte (STT)."""
    from .stt import transcribe_audio
    try:
        body = await request.body()
        if not body:
            return JSONResponse({"error": "No audio data"}, status_code=400)
        
        text = await transcribe_audio(body)
        return JSONResponse({"text": text})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/models")
async def list_models():
    """Liste les modèles free d'opencode disponibles."""
    from .llm import FREE_MODELS, get_current_model
    return {"models": FREE_MODELS, "current": get_current_model()}


class ModelRequest(BaseModel):
    model: str


@app.post("/model")
async def set_model(req: ModelRequest):
    """Change le modèle free utilisé par Alex."""
    from .llm import set_current_model, FREE_MODELS
    if req.model not in FREE_MODELS:
        return JSONResponse({"error": f"Modèle inconnu: {req.model}"}, status_code=400)
    set_current_model(req.model)
    return {"ok": True, "model": req.model}


# ─── Routes Intégrations ────────────────────────────────────────────────────

from .integrations import (
    list_integrations, get_integration_details, execute_action,
    save_credential, get_credential, delete_credential, INTEGRATION_DEFS,
    get_all_logos, get_logo,
)


@app.get("/integrations")
async def get_integrations():
    """Liste les intégrations disponibles."""
    return {"integrations": list_integrations()}


@app.get("/integrations/{name}")
async def get_integration(name: str):
    """Détails d'une intégration."""
    details = get_integration_details(name)
    if not details:
        return JSONResponse({"error": f"Intégration inconnue: {name}"}, status_code=404)
    return details


class IntegrationConnectRequest(BaseModel):
    token: str = ""
    client_id: str = ""
    client_secret: str = ""


@app.post("/integrations/{name}/connect")
async def connect_integration(name: str, req: IntegrationConnectRequest):
    """Connecte une intégration."""
    if name not in INTEGRATION_DEFS:
        return JSONResponse({"error": f"Intégration inconnue: {name}"}, status_code=404)

    config = INTEGRATION_DEFS[name]
    cred_data = {}

    if config.get("auth_type") == "bearer":
        if not req.token:
            return JSONResponse({"error": "Token requis"}, status_code=400)
        cred_data["token"] = req.token
    elif config.get("auth_type") == "oauth2":
        if req.client_id and req.client_secret:
            cred_data["client_id"] = req.client_id
            cred_data["client_secret"] = req.client_secret
        else:
            return JSONResponse({"error": "client_id et client_secret requis"}, status_code=400)

    save_credential(name, cred_data)
    return {"ok": True, "message": f"{config['name']} connecté"}


@app.post("/integrations/{name}/disconnect")
async def disconnect_integration(name: str):
    """Déconnecte une intégration."""
    delete_credential(name)
    return {"ok": True, "message": f"{name} déconnecté"}


class IntegrationActionRequest(BaseModel):
    action: str
    params: dict = {}


@app.post("/integrations/{name}/execute")
async def execute_integration_action(name: str, req: IntegrationActionRequest):
    """Exécute une action sur une intégration."""
    if name not in INTEGRATION_DEFS:
        return JSONResponse({"error": f"Intégration inconnue: {name}"}, status_code=404)

    result = await execute_action(name, req.action, req.params)
    return {"result": result}


# ─── Routes Logos ──────────────────────────────────────────────────────────

@app.get("/logos")
async def list_logos():
    """Liste tous les logos disponibles."""
    return {"logos": get_all_logos()}


@app.get("/logos/{app_name}")
async def get_app_logo(app_name: str):
    """Récupère le logo SVG d'une application."""
    logo = get_logo(app_name)
    if not logo:
        return JSONResponse({"error": f"Logo inconnu: {app_name}"}, status_code=404)
    return {"name": logo["name"], "color": logo["color"], "svg": logo["svg"]}


# ─── Static file serving (for running without Electron / on mobile) ──────────
from starlette.staticfiles import StaticFiles
from starlette.responses import HTMLResponse, FileResponse

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    index_path = os.path.join(ALEX_ROOT, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse("<h1>Alex Brain</h1><p>Backend running.</p>")

@app.get("/mobile", response_class=HTMLResponse)
async def serve_mobile():
    mobile_path = os.path.join(ALEX_ROOT, "mobile.html")
    if os.path.exists(mobile_path):
        return FileResponse(mobile_path, media_type="text/html")
    return HTMLResponse("<h1>Mobile not found</h1>")

# PWA mobile app
PWA_DIR = os.path.join(ALEX_ROOT, "..", "alex-mobile-pwa")
if os.path.isdir(PWA_DIR):
    app.mount("/pwa", StaticFiles(directory=PWA_DIR), name="pwa_static")

# Serve static directories
for _sdir in ["vendor", "node_modules", "data", "boutique", "setting", ".captures"]:
    _sdpath = os.path.join(ALEX_ROOT, _sdir)
    if os.path.isdir(_sdpath):
        try:
            app.mount(f"/{_sdir}", StaticFiles(directory=_sdpath), name=f"static_{_sdir}")
        except Exception:
            pass

@app.get("/{filename:path}")
async def serve_static(filename: str):
    static_exts = ('.html', '.css', '.js', '.json', '.png', '.jpg', '.jpeg', '.svg', '.ico', '.woff', '.woff2', '.ttf', '.mp3', '.ogg')
    if any(filename.endswith(ext) for ext in static_exts):
        fpath = os.path.join(ALEX_ROOT, filename)
        if os.path.isfile(fpath):
            import mimetypes
            mt = mimetypes.guess_type(fpath)[0] or "application/octet-stream"
            return FileResponse(fpath, media_type=mt)
    return JSONResponse({"error": "not found"}, status_code=404)
