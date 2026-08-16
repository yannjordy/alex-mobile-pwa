import asyncio
import json
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from . import tool

CALENDAR_FILE = Path.home() / ".alex_calendar.json"
ALARM_FILE = Path.home() / ".alex_alarms.json"


def _load_calendar() -> list[dict]:
    if CALENDAR_FILE.exists():
        try:
            return json.loads(CALENDAR_FILE.read_text())
        except Exception:
            return []
    return []


def _save_calendar(events: list[dict]):
    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    CALENDAR_FILE.write_text(json.dumps(events, indent=2, ensure_ascii=False))


def _load_alarms() -> list[dict]:
    if ALARM_FILE.exists():
        try:
            return json.loads(ALARM_FILE.read_text())
        except Exception:
            return []
    return []


def _save_alarms(alarms: list[dict]):
    ALARM_FILE.parent.mkdir(parents=True, exist_ok=True)
    ALARM_FILE.write_text(json.dumps(alarms, indent=2, ensure_ascii=False))


def _notify(title: str, message: str):
    """Envoie une notification push système (notify-send)."""
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


@tool("alarme", "Programme ou liste les alarmes. Paramètre : action (add/list/remove), time (HH:MM ou 'dans X minutes' pour add), label (description).")
def alarm(action: str = "list", time: str = "", label: str = "") -> str:
    """Programme ou liste les alarmes.

    Args:
        action: Action à effectuer (add, list, remove).
        time: Heure de l'alarme (HH:MM ou 'dans X minutes') pour add.
        label: Description ou titre de l'alarme.
    """
    alarms = _load_alarms()
    if action == "list":
        if not alarms:
            return "Aucune alarme programmée."
        lines = ["🔔 Alarmes enregistrées :"]
        for i, a in enumerate(alarms, 1):
            lines.append(f"  {i}. {a['time']} — {a.get('label', 'Sans titre')}")
        return "\n".join(lines)

    if action == "add":
        if not time:
            return "Il me faut une heure (HH:MM) pour l'alarme."
        target = _resolve_time(time)
        alarms.append({
            "time": target,
            "label": label or "Réveil",
            "created": datetime.now().isoformat(),
            "fired": False,
        })
        _save_alarms(alarms)
        _notify("Alex ⏰", f"Alarme programmée à {target} — {label or 'Réveil'}")
        return f"Alarme programmée à {target} — {label or 'Réveil'} ✓"

    if action == "remove":
        if not time:
            return "Quelle alarme veux-tu supprimer ? (donne l'heure)"
        alarms = [a for a in alarms if a["time"] != time]
        _save_alarms(alarms)
        return f"Alarme à {time} supprimée ✓"

    return "Actions disponibles : add (HH:MM ou 'dans X minutes'), list, remove (HH:MM)"


def check_due_alarms():
    """Déclenche les alarmes dont l'heure est atteinte (appelé périodiquement)."""
    alarms = _load_alarms()
    if not alarms:
        return []
    
    now = datetime.now()
    now_minutes = now.hour * 60 + now.minute
    fired = []
    remaining = []
    
    for a in alarms:
        target = _resolve_time(a.get("time", ""))
        a["time"] = target
        
        # Convert target to minutes for comparison
        m = re.search(r"(\d+):(\d+)", target)
        if m:
            target_minutes = int(m.group(1)) * 60 + int(m.group(2))
        else:
            remaining.append(a)
            continue
        
        # Fire if target time has passed (within the last minute or overdue)
        if target_minutes <= now_minutes:
            fired.append(a)
        else:
            remaining.append(a)
    
    if fired:
        _save_alarms(remaining)
        for a in fired:
            label = a.get('label', 'Réveil')
            _notify("Alex ⏰", f"{label} — il est {now.strftime('%H:%M')} !")
    return fired


async def _check_due_alarms_async():
    """Wrapper async pour check_due_alarms (aucune opération bloquante lourde)."""
    return check_due_alarms()


def _notify_from_thread(title: str, message: str):
    try:
        subprocess.run(["notify-send", title, message], timeout=3)
    except Exception:
        pass


@tool("calendrier", "Gère les événements du calendrier local. Paramètre : action (add/list/remove/today), date (JJ/MM), time, title, description.")
def calendar_tool(action: str = "today", date: str = "", time: str = "",
                  title: str = "", description: str = "") -> str:
    """Gère les événements du calendrier local.

    Args:
        action: Action à effectuer (add, list, today, remove).
        date: Date de l'événement au format JJ/MM.
        time: Heure de l'événement.
        title: Titre de l'événement.
        description: Description détaillée de l'événement.
    """
    events = _load_calendar()

    if action == "today":
        today = datetime.now().strftime("%d/%m")
        today_events = [e for e in events if e.get("date") == today]
        if not today_events:
            return "Rien de prévu aujourd'hui 📅"
        lines = ["📅 Aujourd'hui :"]
        for e in today_events:
            t = e.get("time", "")
            lines.append(f"  {t or '—'} {e['title']}")
        return "\n".join(lines)

    if action == "list":
        if not events:
            return "Calendrier vide."
        lines = ["📅 Événements :"]
        for e in sorted(events, key=lambda x: x.get("date", "") + x.get("time", "")):
            d = e.get("date", "??")
            t = e.get("time", "")
            lines.append(f"  {d} {t or '—'} {e['title']}")
        return "\n".join(lines)

    if action == "add":
        if not title:
            return "Quel est le titre de l'événement ?"
        events.append({
            "date": date or datetime.now().strftime("%d/%m"),
            "time": time or "",
            "title": title,
            "description": description or "",
        })
        _save_calendar(events)
        _notify("Alex 📅", f"Événement programmé : {title}")
        return f"Événement ajouté : {title} le {date or 'aujourd\'hui'} ✓"

    if action == "remove":
        if not title:
            return "Quel événement veux-tu supprimer ?"
        events = [e for e in events if e["title"].lower() != title.lower()]
        _save_calendar(events)
        return f"Événement « {title} » supprimé ✓"

    return "Actions : add, list, today, remove"


@tool("notifications", "Lit les notifications système récentes (via Dunst ou notify-send).")
def read_notifications() -> str:
    """Lit les notifications système récentes.
    """
    # Try reading Dunst history
    try:
        result = subprocess.run(
            ["dunstctl", "history"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output and output != "[]":
                # Parse and summarize notifications
                try:
                    notifications = json.loads(output)
                    if not notifications:
                        return "Aucune notification récente."
                    
                    summary = []
                    for n in notifications[:5]:  # Last 5 notifications
                        app_name = n.get("app_name", "Système")
                        summary_text = n.get("summary", "")
                        body = n.get("body", "")
                        
                        # Create a natural summary
                        if summary_text:
                            summary.append(f"• {app_name}: {summary_text}")
                        elif body:
                            summary.append(f"• {app_name}: {body[:100]}")
                    
                    if summary:
                        return "🔔 Dernières notifications :\n" + "\n".join(summary)
                except json.JSONDecodeError:
                    # If JSON parsing fails, return raw output
                    return f"🔔 Notifications récentes :\n{output[:2000]}"
    except Exception:
        pass

    # Try reading from journal
    try:
        result = subprocess.run(
            ["journalctl", "--user", "-n", "10", "--no-pager", "-t", "notify-send"],
            capture_output=True, text=True, timeout=5
        )
        if result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            return "🔔 Notifications récentes :\n" + "\n".join(lines[-10:])
    except Exception:
        pass

    return "Aucune notification récente trouvée."


@tool("notification_envoyer", "Envoie une notification système. Paramètre : title, message.")
def send_notification(title: str = "Alex", message: str = "") -> str:
    """Envoie une notification système.

    Args:
        title: Titre de la notification.
        message: Corps du message de la notification.
    """
    if not message:
        return "Que veux-tu que je notifie ?"
    try:
        subprocess.run(
            ["notify-send", title, message],
            timeout=3
        )
        return "Notification envoyée ✓"
    except Exception as e:
        return f"Impossible d'envoyer la notification : {e}"
