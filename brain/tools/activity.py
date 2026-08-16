"""Journal d'activité temps réel (commandes, tool calls, états, transferts).

Le frontend interroge /activity pour afficher un « terminal » des actions en
cours : chaque commande exécutée, chaque outil appelé, chaque changement
d'état est consigné avec horodatage et niveau (info/success/warn/error/cmd).
"""

from __future__ import annotations

import time
import threading

_lock = threading.Lock()
_events: list[dict] = []
_MAX = 400


def log(level: str, message: str, source: str = "brain") -> None:
    """Consigne un événement. level ∈ {cmd, info, success, warn, error}."""
    if not message:
        return
    with _lock:
        _events.append({
            "t": time.time(),
            "level": level,
            "message": str(message)[:2000],
            "source": source,
        })
        if len(_events) > _MAX:
            del _events[:-_MAX]


def snapshot(limit: int = 120) -> list[dict]:
    with _lock:
        return list(_events[-limit:])


def clear() -> None:
    with _lock:
        _events.clear()
