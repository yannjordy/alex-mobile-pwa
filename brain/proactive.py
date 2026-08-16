"""Système proactif : Alex agit sans qu'on lui parle."""
import asyncio
import time
from typing import Callable, Optional

from . import tools as tools_registry
from .tools import downloads as _tools_downloads
from .tools import automation as _tools_automation
from .tools import scheduler as _tools_scheduler


_proactive_state = {
    "greeting_sent": False,
    "last_download_check": 0,
    "last_system_check": 0,
    "last_reminder_check": 0,
    "last_task_check": 0,
}

_broadcast_fn: Optional[Callable] = None
_push_fn: Optional[Callable] = None


def init(broadcast_fn: Callable, push_fn: Callable):
    global _broadcast_fn, _push_fn
    _broadcast_fn = broadcast_fn
    _push_fn = push_fn


async def send_proactive_message(text: str):
    if _broadcast_fn:
        await _broadcast_fn("proactive_message", {"text": text})


async def check_downloads():
    now = time.time()
    if now - _proactive_state["last_download_check"] < 10:
        return
    _proactive_state["last_download_check"] = now
    try:
        status = _tools_downloads.manager.snapshot()
        if status and status.get("active"):
            for dl in status["active"]:
                if dl.get("status") == "done":
                    _push_fn("Alex 📥", f"« {dl.get('title', 'Téléchargement')} » terminé !")
                elif dl.get("status") == "error":
                    _push_fn("Alex ⚠️", f"Échec de « {dl.get('title', 'Téléchargement')} »")
    except Exception:
        pass


async def check_system():
    now = time.time()
    if now - _proactive_state["last_system_check"] < 300:
        return
    _proactive_state["last_system_check"] = now
    try:
        bat = await tools_registry.execute("batterie", {})
        bat_str = str(bat)
        if "100%" not in bat_str and "AC" not in bat_str:
            import re
            bat_m = re.search(r'(\d+)%', bat_str)
            if bat_m:
                pct = int(bat_m.group(1))
                if pct <= 15:
                    _push_fn("Alex 🔋", f"Batterie critique : {pct}% ! Branche ton chargeur.")
                elif pct <= 30:
                    _push_fn("Alex 🔋", f"Batterie à {pct}%. Pense à brancher.")
    except Exception:
        pass


async def check_reminders():
    now = time.time()
    if now - _proactive_state["last_reminder_check"] < 60:
        return
    _proactive_state["last_reminder_check"] = now
    try:
        alarms = await tools_registry.execute("alarme", {"action": "list"})
        if alarms and "Aucune" not in str(alarms):
            text = str(alarms)
            announced = _proactive_state.setdefault("announced_alarms", set())
            alarm_hash = hash(text)
            if alarm_hash not in announced:
                announced.add(alarm_hash)
                _push_fn("Alex ⏰", f"Tu as des alarmes prévues :\n{text}")
            announced.intersection_update({hash(str(alarms))})
        else:
            _proactive_state.setdefault("announced_alarms", set()).clear()
    except Exception:
        pass


async def check_scheduled_tasks():
    """Vérifie et exécute les tâches programmées."""
    now = time.time()
    if now - _proactive_state["last_task_check"] < 30:
        return
    _proactive_state["last_task_check"] = now
    try:
        fired = _tools_scheduler.check_due_tasks()
        if fired:
            for task in fired:
                _push_fn("Alex 🤖", f"Tâche exécutée : {task.get('label', '')}")
            # Broadcast task update to frontend
            if _broadcast_fn:
                tasks = _tools_scheduler._load_tasks()
                pending_count = len([t for t in tasks if not t.get("executed")])
                await _broadcast_fn("task_update", {"pending_count": pending_count})
    except Exception as e:
        print(f"[proactive] Erreur tâches programmées: {e}")


async def proactive_loop():
    await asyncio.sleep(5)
    print("[proactive] Système proactif démarré")
    while True:
        try:
            await check_downloads()
            await check_system()
            await check_reminders()
            await check_scheduled_tasks()
        except Exception as e:
            print(f"[proactive] Erreur: {e}")
        await asyncio.sleep(30)
