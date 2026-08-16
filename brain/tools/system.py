import asyncio
import os
import platform
import shutil
import subprocess
from pathlib import Path

from . import tool
from .downloads import classify, run_tracked
from . import activity


@tool("info_systeme", "Affiche les informations sur le système (CPU, RAM, disque, OS).")
def system_info() -> str:
    """Affiche les informations sur le système (CPU, RAM, disque, OS).
    """
    cpu = platform.processor() or "inconnu"
    node = platform.node()
    system = platform.system()
    release = platform.release()
    mem = _get_memory()
    disk = _get_disk()
    return (
        f"🖥 {node} — {system} {release}\n"
        f"⚡ CPU: {cpu} ({os.cpu_count()} threads)\n"
        f"💾 RAM: {mem}\n"
        f"💿 Disque: {disk}"
    )


@tool("processus", "Liste les processus en cours d'exécution.")
def process_list(count: int = 20) -> str:
    """Liste les processus en cours d'exécution.

    Args:
        count: Nombre maximum de processus à afficher (triés par mémoire).
    """
    try:
        result = subprocess.run(
            ["ps", "aux", "--sort=-%mem"],
            capture_output=True, text=True, timeout=5
        )
        lines = result.stdout.strip().splitlines()
        header = lines[0] if lines else ""
        rows = lines[1:count + 1]
        formatted = []
        for row in rows:
            parts = row.split(None, 10)
            if len(parts) >= 11:
                user, pid, cpu, mem, vsz, rss, tty, stat, start, time, cmd = parts
                formatted.append(f"{pid:>6} {cpu:>4}% {mem:>4}% {cmd[:60]}")
        return f"📊 Processus (top {count} par mémoire):\n" + ("USER     PID   CPU  MEM COMMAND\n" + "\n".join(formatted) if formatted else result.stdout[:3000])
    except Exception as e:
        return f"Erreur de liste des processus : {e}"


@tool("commande", "Exécute une commande bash et retourne le résultat. Utile pour tout contrôle système.", dangerous=True)
async def run_command(command: str) -> str:
    """Exécute une commande bash et retourne le résultat.

    Args:
        command: Commande bash à exécuter.
    """
    # Téléchargements / installations → exécution suivie avec progression temps réel
    if classify(command):
        activity.log("cmd", command, source="terminal")
        iid, status, out = await run_tracked(command)
        label = "Terminé" if status == "done" else ("Échec" if status == "error" else "Annulé")
        activity.log("success" if status == "done" else "error", f"{command[:80]} → {label}", source="terminal")
        return f"[transfert {iid}] {label}\n{out}"
    activity.log("cmd", command, source="terminal")
    try:
        result = await asyncio.to_thread(
            lambda: subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=120
            )
        )
        out = (result.stdout or "")[:8000]
        err = (result.stderr or "")[:1000]
        parts = []
        if out:
            parts.append(out)
        if err:
            parts.append(f"[stderr]\n{err}")
        ret = "\n".join(parts)
        activity.log("success", f"{command[:80]} → (rc {result.returncode})", source="terminal")
        if ret.strip():
            activity.log("info", ret[:300], source="terminal")
        return ret if ret else "(aucune sortie)"
    except subprocess.TimeoutExpired:
        activity.log("error", f"{command[:80]} → délai 120s dépassé", source="terminal")
        return "Commande interrompue (délai de 120s dépassé)."
    except Exception as e:
        activity.log("error", f"{command[:80]} → {e}", source="terminal")
        return f"Erreur d'exécution : {e}"


@tool("ouvrir_application", "Cherche et lance une application sur l'ordinateur. Paramètre : nom (nom de l'app, ex: firefox, vscode, calculatrice).")
def launch_application(nom: str) -> str:
    """Cherche et lance une application sur l'ordinateur.

    Args:
        nom: Nom de l'application à lancer (ex: firefox, vscode, calculatrice).
    """
    if not nom or not nom.strip():
        return "Quelle application veux-tu lancer ?"
    name = nom.strip().lower()

    # Chercher dans les .desktop files
    desktop_dirs = [
        Path.home() / ".local" / "share" / "applications",
        Path("/usr/share/applications"),
        Path("/usr/local/share/applications"),
    ]
    matches = []
    for ddir in desktop_dirs:
        if not ddir.exists():
            continue
        for f in ddir.glob("*.desktop"):
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if "NoDisplay=true" in content:
                continue
            fname = f.stem.lower()
            if name in fname:
                for line in content.splitlines():
                    if line.startswith("Name="):
                        display = line.split("=", 1)[1].strip()
                        break
                else:
                    display = fname
                matches.append((fname, display, str(f)))

    # Chercher dans PATH
    if not matches:
        for pdir in os.environ.get("PATH", "").split(":"):
            p = Path(pdir) / name
            if p.exists() and os.access(str(p), os.X_OK):
                try:
                    subprocess.Popen([str(p)], start_new_session=True)
                    return f"Lancement de {name}..."
                except Exception as e:
                    return f"Impossible de lancer {name} : {e}"

    if matches:
        best = matches[0]
        name_match, display, path = best
        try:
            subprocess.Popen(["gtk-launch", name_match], start_new_session=True)
            return f"Je lance {display}..."
        except FileNotFoundError:
            try:
                subprocess.Popen(["xdg-open", path], start_new_session=True)
                return f"Je lance {display}..."
            except Exception:
                try:
                    subprocess.Popen([path], start_new_session=True)
                    return f"Je lance {display}..."
                except Exception as e:
                    return f"Impossible de lancer {display} : {e}"

    # Dernier recours : essayer de lancer directement
    try:
        subprocess.Popen([name], start_new_session=True)
        return f"Tentative de lancement de {name}..."
    except Exception:
        pass

    apps_trouvees = ", ".join(m[1] for m in matches[:10]) if matches else ""
    if apps_trouvees:
        return f"Je n'ai pas trouvé « {nom} ». Applications disponibles : {apps_trouvees}."
    return f"Je n'ai pas trouvé d'application « {nom} »."


def _get_memory() -> str:
    try:
        import psutil
        mem = psutil.virtual_memory()
        total = mem.total / (1024**3)
        avail = mem.available / (1024**3)
        return f"{avail:.1f} Go libre / {total:.1f} Go total"
    except ImportError:
        try:
            with open("/proc/meminfo") as f:
                data = f.read()
            total = _parse_meminfo(data, "MemTotal")
            avail = _parse_meminfo(data, "MemAvailable")
            if total:
                return f"{avail:.1f} Go libre / {total:.1f} Go total"
        except Exception:
            pass
        return "indisponible"


def _get_disk() -> str:
    try:
        total, used, free = shutil.disk_usage("/")
        return f"{free / (1024**3):.0f} Go libre / {total / (1024**3):.0f} Go total"
    except Exception:
        return "indisponible"


def _parse_meminfo(data: str, key: str) -> float:
    for line in data.splitlines():
        if line.startswith(key + ":"):
            kb = int(line.split()[1])
            return kb / (1024 * 1024)
    return 0


# --- Workflow multi-étapes ---

from .workflow import workflow_manager, create_step, StepStatus


@tool("workflow_start", "Lance un workflow multi-étapes. Chaque étape est une commande CLI ou une action.",
      dangerous=True)
async def workflow_start(title: str, steps_json: str, context_json: str = "{}") -> str:
    """Démarre un workflow avec plusieurs étapes.

    Args:
        title: Titre du workflow (ex: "Déployer mon projet")
        steps_json: Liste JSON des étapes. Chaque étape: {"id":"...", "title":"...", "command":"..."}
        context_json: Contexte partagé entre étapes (JSON)
    """
    import json
    try:
        steps_data = json.loads(steps_json)
        context = json.loads(context_json) if context_json else {}
    except json.JSONDecodeError as e:
        return f"Erreur de format JSON : {e}"

    steps = []
    for s in steps_data:
        step = create_step(
            id=s.get("id", f"step-{len(steps)+1}"),
            title=s.get("title", "Étape"),
            command=s.get("command"),
            requires_confirmation=s.get("requires_confirmation", True),
            depends_on=s.get("depends_on")
        )
        steps.append(step)

    if not steps:
        return "Aucune étape fournie."

    wf = workflow_manager.create_workflow(title, steps, context)
    activity.log("cmd", f"workflow_start: {title} ({len(steps)} étapes)", source="tools")
    return json.dumps({
        "workflow_id": wf.id,
        "title": title,
        "total_steps": len(steps),
        "steps": [{"id": s.id, "title": s.title, "command": s.command} for s in steps]
    }, ensure_ascii=False)


@tool("workflow_step", "Exécute l'étape courante (ou une étape spécifique) d'un workflow.",
      dangerous=True)
async def workflow_step(workflow_id: str, step_index: int = -1) -> str:
    """Exécute une étape du workflow.

    Args:
        workflow_id: Identifiant du workflow
        step_index: Index de l'étape à exécuter (-1 = étape courante)
    """
    import json
    idx = step_index if step_index >= 0 else None
    result = await workflow_manager.execute_step(workflow_id, idx)
    return json.dumps(result, ensure_ascii=False)


@tool("workflow_status", "Affiche le statut d'un workflow (étapes, progression, résultats).")
async def workflow_status(workflow_id: str) -> str:
    """Retourne le statut détaillé d'un workflow.

    Args:
        workflow_id: Identifiant du workflow
    """
    import json
    status = workflow_manager.get_status(workflow_id)
    return json.dumps(status, ensure_ascii=False)


@tool("workflow_pause", "Met en pause un workflow (en attente de décision utilisateur).")
async def workflow_pause(workflow_id: str, reason: str = "En attente de décision") -> str:
    """Met en pause un workflow.

    Args:
        workflow_id: Identifiant du workflow
        reason: Raison de la pause
    """
    ok = workflow_manager.pause_workflow(workflow_id, reason)
    if ok:
        activity.log("info", f"workflow_pause: {workflow_id} — {reason}", source="tools")
        return f"Workflow mis en pause : {reason}"
    return "Workflow non trouvé ou déjà terminé."


@tool("workflow_resume", "Reprend un workflow mis en pause.")
async def workflow_resume(workflow_id: str) -> str:
    """Reprend un workflow en pause.

    Args:
        workflow_id: Identifiant du workflow
    """
    ok = workflow_manager.resume_workflow(workflow_id)
    if ok:
        activity.log("info", f"workflow_resume: {workflow_id}", source="tools")
        return "Workflow repris."
    return "Workflow non trouvé ou non en pause."


@tool("workflow_cancel", "Annule un workflow en cours.")
async def workflow_cancel(workflow_id: str) -> str:
    """Annule un workflow.

    Args:
        workflow_id: Identifiant du workflow
    """
    ok = workflow_manager.cancel_workflow(workflow_id)
    if ok:
        activity.log("warn", f"workflow_cancel: {workflow_id}", source="tools")
        return "Workflow annulé."
    return "Workflow non trouvé."


@tool("workflow_skip", "Passe l'étape courante d'un workflow.")
async def workflow_skip(workflow_id: str, step_index: int = -1) -> str:
    """Passe une étape du workflow.

    Args:
        workflow_id: Identifiant du workflow
        step_index: Index de l'étape à passer (-1 = courante)
    """
    idx = step_index if step_index >= 0 else None
    ok = workflow_manager.skip_step(workflow_id, idx)
    if ok:
        return "Étape passée."
    return "Impossible de passer cette étape."


@tool("workflow_list", "Liste les workflows actifs.")
async def workflow_list() -> str:
    """Liste tous les workflows actifs."""
    import json
    active = workflow_manager.list_active()
    if not active:
        return "Aucun workflow actif."
    result = []
    for wf in active:
        result.append({
            "id": wf.id,
            "title": wf.title,
            "status": wf.status,
            "current_step": wf.current_step_index,
            "total_steps": len(wf.steps)
        })
    return json.dumps(result, ensure_ascii=False)
