import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from . import tool

TASKS_FILE = Path.home() / ".alex_scheduled_tasks.json"


def _load_tasks() -> list[dict]:
    if TASKS_FILE.exists():
        try:
            return json.loads(TASKS_FILE.read_text())
        except Exception:
            return []
    return []


def _save_tasks(tasks: list[dict]):
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.write_text(json.dumps(tasks, indent=2, ensure_ascii=False))


def _notify(title: str, message: str):
    """Envoie une notification push système."""
    try:
        subprocess.run(["notify-send", title, message], timeout=3)
    except Exception:
        pass


def _resolve_time(value: str) -> str:
    """Convertit '07:30' ou 'dans 5 minutes' en heure cible 'HH:MM'."""
    value = value.strip()
    m = re.search(r"([01]?\d|2[0-3])[:hH]([0-5]\d)", value)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    m = re.search(r"(\d+)\s*(?:min|minutes?|mn)", value, re.IGNORECASE)
    if m:
        return (datetime.now() + timedelta(minutes=int(m.group(1)))).strftime("%H:%M")
    m = re.search(r"(\d+)\s*(?:h|heures?)", value, re.IGNORECASE)
    if m:
        return (datetime.now() + timedelta(hours=int(m.group(1)))).strftime("%H:%M")
    return value


def _execute_action(action: dict) -> str:
    """Exécute une action automatisée."""
    action_type = action.get("type", "")
    
    if action_type == "wallpaper":
        path = action.get("path", "")
        if path:
            try:
                from .desktop import set_wallpaper
                return set_wallpaper(path)
            except Exception as e:
                return f"Erreur fond d'écran: {e}"
    
    elif action_type == "bluetooth":
        state = action.get("state", "on")
        try:
            if state == "on":
                subprocess.run(["bluetoothctl", "power", "on"], timeout=5)
                return "Bluetooth activé ✓"
            else:
                subprocess.run(["bluetoothctl", "power", "off"], timeout=5)
                return "Bluetooth désactivé ✓"
        except Exception as e:
            return f"Erreur Bluetooth: {e}"
    
    elif action_type == "app":
        app = action.get("name", "")
        if app:
            try:
                subprocess.Popen([app])
                return f"Application {app} lancée ✓"
            except Exception as e:
                return f"Erreur lancement {app}: {e}"
    
    elif action_type == "volume":
        level = action.get("level", "50")
        try:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], timeout=3)
            return f"Volume réglé à {level}% ✓"
        except Exception as e:
            return f"Erreur volume: {e}"
    
    elif action_type == "brightness":
        level = action.get("level", "50")
        try:
            subprocess.run(["brightnessctl", "set", f"{level}%"], timeout=5)
            return f"Luminosité réglée à {level}% ✓"
        except Exception as e:
            return f"Erreur luminosité: {e}"
    
    elif action_type == "command":
        cmd = action.get("command", "")
        if cmd:
            try:
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                return f"Commande exécutée: {result.stdout[:200]}" if result.stdout else "Commande exécutée ✓"
            except Exception as e:
                return f"Erreur commande: {e}"
    
    elif action_type == "notify":
        title = action.get("title", "Alex")
        message = action.get("message", "")
        _notify(title, message)
        return f"Notification envoyée: {message} ✓"
    
    return "Type d'action inconnu"


@tool("tache_programmee", 
      "Programme une tâche automatisée. Paramètres : action (add/list/remove/run_now), "
      "time (HH:MM ou 'dans X minutes'), task_type (wallpaper/bluetooth/app/volume/brightness/command/notify), "
      "params (JSON des paramètres de l'action), label (description).")
def scheduled_task(action: str = "list", time: str = "", task_type: str = "", 
                   params: str = "", label: str = "") -> str:
    """Programme ou gère des tâches automatisées.
    
    Args:
        action: Action à effectuer (add, list, remove, run_now).
        time: Heure d'exécution (HH:MM ou 'dans X minutes') pour add.
        task_type: Type de tâche (wallpaper, bluetooth, app, volume, brightness, command, notify).
        params: Paramètres JSON de l'action (ex: '{"path": "/path/to/image.jpg"}').
        label: Description de la tâche.
    """
    tasks = _load_tasks()
    
    if action == "list":
        if not tasks:
            return "Aucune tâche programmée."
        lines = ["🤖 Tâches programmées :"]
        for i, t in enumerate(tasks, 1):
            status = "⏳" if not t.get("executed") else "✅"
            lines.append(f"  {status} {i}. {t.get('time', '??')} — {t.get('label', 'Sans titre')} ({t.get('task_type', 'inconnu')})")
        return "\n".join(lines)
    
    if action == "add":
        if not time or not task_type:
            return "Il me faut une heure et un type de tâche."
        
        target_time = _resolve_time(time)
        task_params = {}
        if params:
            try:
                task_params = json.loads(params)
            except json.JSONDecodeError:
                return "Format JSON invalide pour les paramètres."
        
        tasks.append({
            "time": target_time,
            "task_type": task_type,
            "params": task_params,
            "label": label or f"Tâche {task_type}",
            "created": datetime.now().isoformat(),
            "executed": False,
        })
        _save_tasks(tasks)
        _notify("Alex 🤖", f"Tâche programmée à {target_time} — {label or task_type}")
        return f"Tâche programmée à {target_time} — {label or task_type} ✓"
    
    if action == "remove":
        if not label:
            return "Quelle tâche veux-tu supprimer ? (donne le label)"
        tasks = [t for t in tasks if t.get("label", "").lower() != label.lower()]
        _save_tasks(tasks)
        return f"Tâche « {label} » supprimée ✓"
    
    if action == "run_now":
        if not task_type:
            return "Quel type de tâche veux-tu exécuter ?"
        task_params = {}
        if params:
            try:
                task_params = json.loads(params)
            except json.JSONDecodeError:
                return "Format JSON invalide pour les paramètres."
        
        result = _execute_action({"type": task_type, **task_params})
        return f"Exécution immédiate : {result}"
    
    return "Actions disponibles : add, list, remove, run_now"


def check_due_tasks():
    """Vérifie et exécute les tâches dont l'heure est atteinte."""
    tasks = _load_tasks()
    if not tasks:
        return []
    
    now = datetime.now().strftime("%H:%M")
    fired = []
    remaining = []
    
    for t in tasks:
        if t.get("executed"):
            remaining.append(t)
            continue
        
        target = _resolve_time(t.get("time", ""))
        t["time"] = target
        
        if target == now:
            # Exécuter la tâche
            result = _execute_action({"type": t.get("task_type", ""), **t.get("params", {})})
            t["executed"] = True
            t["result"] = result
            fired.append(t)
            _notify("Alex 🤖", f"Tâche exécutée : {t.get('label', '')} — {result}")
        else:
            remaining.append(t)
    
    if fired:
        _save_tasks(remaining)
    
    return fired


@tool("rappel_intelligent", 
      "Crée un rappel intelligent avec contexte. Paramètres : time (HH:MM ou 'dans X minutes'), "
      "message (contenu du rappel), context (optionnel : contexte supplémentaire).")
def smart_reminder(time: str = "", message: str = "", context: str = "") -> str:
    """Crée un rappel intelligent avec contexte.
    
    Args:
        time: Heure du rappel (HH:MM ou 'dans X minutes').
        message: Contenu du rappel.
        context: Contexte supplémentaire (optionnel).
    """
    if not time or not message:
        return "Il me faut une heure et un message pour le rappel."
    
    target_time = _resolve_time(time)
    
    # Créer une notification programée
    tasks = _load_tasks()
    tasks.append({
        "time": target_time,
        "task_type": "notify",
        "params": {
            "title": "Alex 📝",
            "message": message,
        },
        "label": f"Rappel: {message[:50]}",
        "created": datetime.now().isoformat(),
        "executed": False,
        "context": context,
    })
    _save_tasks(tasks)
    
    _notify("Alex 📝", f"Rappel programmé à {target_time} — {message}")
    return f"Rappel programmé à {target_time} — {message} ✓"
