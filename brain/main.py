"""Alex Brain — Point d'entrée principal (modulaire).

Ce fichier importe les modules séparés et expose l'application FastAPI.
Pour la compatibilité, les symboles principaux sont ré-exportés ici.
"""
import asyncio
import json
import os
import re
import time
from typing import Optional

# Charger .env s'il existe
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# ─── Imports modulaires ──────────────────────────────────────────────────────
from .config import (
    OPENCODE_API_URL,
    USER_NAME,
)
from .prompts import (
    SYSTEM_PROMPT, COMPACT_SYSTEM_PROMPT, AGENT_LOOP_PROMPT,
    COMPLEXITY_WORDS, TOOL_PROMPT, ESSENTIAL_TOOLS,
    AUTONOMOUS_TOOLS, DANGEROUS_TOOLS,
)
from . import llm
from . import session
from . import proactive
from .utils import estimate_complexity, is_polluted_conversation
from .routes import app, _broadcast_event, _push_notification

# ─── Imports tools (nécessaires pour le fonctionnement) ──────────────────────
from . import wake_word
from . import tools as tools_registry
from .tools import files as _tools_files
from .tools import system as _tools_system
from .tools import web as _tools_web
from .tools import weather as _tools_weather
from .tools import automation as _tools_automation
from .tools import desktop as _tools_desktop
from .tools import devices as _tools_devices
from .tools import downloads as _tools_downloads
from .tools import network as _tools_network
from .tools import mcp as _tools_mcp
from .tools import selfprogramming as _tools_selfprogramming
from .tools import activity as _tools_activity
from .tools import scheduler as _tools_scheduler
from .tools import website as _tools_website
from .tools import security as _tools_security
from .tools import workflows as _tools_workflows
from . import memory
from .skills.manager import skill_manager
from .tools import position as _tools_position
from .tools import map as _tools_map
from .workflow.routes import router as workflow_router

# ─── Enregistrer le routeur workflow ────────────────────────────────────────
app.include_router(workflow_router)

# ─── Variables compat ────────────────────────────────────────────────────────
_current_model = os.environ.get("ALEX_LOCAL_MODEL", "alex:latest")


# ─── Export public (backward compat) ─────────────────────────────────────────
__all__ = [
    "app",
    "OLLAMA_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL",
    "OPENCODE_API_URL",
    "USER_NAME",
    "SYSTEM_PROMPT", "COMPACT_SYSTEM_PROMPT", "AGENT_LOOP_PROMPT",
    "estimate_complexity", "is_polluted_conversation",
    "llm", "session", "proactive",
    "tools_registry", "memory", "skill_manager",
]
