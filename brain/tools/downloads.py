"""Gérard de téléchargements/installations visibles en temps réel dans l'interface.

Le DownloadsManager tient un registre en mémoire des transferts actifs/récents.
Le frontend interroge /downloads/status pour afficher des widgets de progression
discrets pendant qu'Alex continue de discuter.
"""

from __future__ import annotations

import asyncio
import os
import re
import time

from . import activity

_desc_dir = os.path.join(os.path.expanduser("~"), "Téléchargements")

# Patterns de progression (pourcentage, vitesse)
_pct_re = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
# curl progress: "100  100k  100  100k    0     0  10744      0  0:00:09  0:00:09 --:--:-- 17221"
# The LAST number on the line is speed in bytes/s
_curl_speed_re = re.compile(r"(\d+)\s*$")


def _parse_line(line: str):
    """Retourne (percent, speed) extraits d'une ligne/fragment de sortie."""
    s = line.strip("\x1b[0K").strip()
    if not s:
        return None, None

    percent = None
    # curl progress lines start with a percentage: " 15  100k   15 16236 ..."
    curl_pct = re.match(r"\s*(\d{1,3})\s+\d", s)
    if curl_pct:
        p = int(curl_pct.group(1))
        if 0 <= p <= 100:
            percent = p

    if percent is None:
        pct = _pct_re.search(s)
        if pct:
            try:
                p = float(pct.group(1))
                if 0 <= p <= 100:
                    percent = int(p)
            except ValueError:
                pass

    speed = None
    # curl progress: last number on the line = speed in bytes/s
    m = _curl_speed_re.search(s)
    if m:
        try:
            v = int(m.group(1))
            if v >= 1024 * 1024:
                speed = f"{v / 1024 / 1024:.1f}MB/s"
            elif v >= 1024:
                speed = f"{v / 1024:.1f}KB/s"
            elif v > 0:
                speed = f"{v}B/s"
        except ValueError:
            pass

    return percent, speed


def classify(command: str):
    """Classe une commande comme transfert. Retourne (kind, libellé) ou None."""
    c = command.lower()
    if re.search(r"\b(curl|wget|yt-dlp|aria2c|wget2)\b", c):
        return ("download", "Téléchargement")
    if re.search(r"\b(apt(-get)?|dnf|yum|pacman|zypper)\b.*\b(install|update|upgrade)\b", c) \
            or re.search(r"\b(dpkg\s+-i|snap\s+install|flatpak\s+install)\b", c):
        return ("install", "Installation")
    if re.search(r"\b(pip|pip3|pipx|uv\s+pip|poetry|pipenv)\b.*\binstall\b", c):
        return ("install", "Installation Python")
    if re.search(r"\b(npm|pnpm|yarn)\b.*\b(install|add)\b", c):
        return ("install", "Installation npm")
    if re.search(r"\bgit\s+clone\b", c):
        return ("download", "Clonage Git")
    if re.search(r"\bdocker\s+(pull|build|push|run|compose|save|load)\b", c):
        return ("install", "Opération Docker")
    if re.search(r"\b(kubectl|helm|k3s|k9s)\s+(apply|create|delete|install|upgrade|rollout|scale|wait|port-forward|run|logs)\b", c):
        return ("install", "Opération Kubernetes")
    if re.search(r"\bsupabase\s+(db\s+(push|diff|reset)|functions\s+deploy|start|stop)\b", c):
        return ("install", "Opération Supabase")
    if re.search(r"\bgh\s+(pr\s+(merge|create)|issue\s+create|repo\s+clone)\b", c):
        return ("install", "Opération GitHub")
    if re.search(r"\b(nvidia-smi|systemctl|journalctl|psql|mysql|redis-cli)\b", c):
        return ("install", "Commande système")
    return None


def title_for(kind: str, command: str) -> str:
    c = command.strip()
    m = re.search(r"-[oO]\s+([\w./~\-]+)|--output\s+([\w./~\-]+)|-O\s", c)
    if m:
        return (m.group(1) or m.group(2)) or "fichier"
    m = re.search(r"\b(install|add)\s+(.*)$", c)
    if m:
        args = m.group(2).split()
        pkg = next((a for a in args if a and not a.startswith("-")),
                   next(iter(args), ""))
        return pkg or "paquet"
    m = re.search(r"\bclone\s+([^\s]+)", c)
    if m:
        return m.group(1).split("/")[-1].replace(".git", "")
    for p in reversed(c.split()):
        if p.startswith("http"):
            return p.split("/")[-1].split("?")[0] or p
    return c[:40]


class DownloadsManager:
    def __init__(self, max_items: int = 8):
        self._items: dict[str, dict] = {}
        self._order: list[str] = []
        self._seq = 0
        self._max_items = max_items

    def _new_id(self) -> str:
        self._seq += 1
        return f"dl-{int(time.time())}-{self._seq}"

    def start(self, kind: str, title: str, command: str) -> str:
        iid = self._new_id()
        item = {
            "id": iid, "kind": kind, "title": title, "command": command,
            "status": "running", "percent": None, "speed": None,
            "last_line": "", "lines": [],
            "started_at": time.time(), "finished_at": None, "error": None,
        }
        self._items[iid] = item
        self._order.append(iid)
        if len(self._order) > self._max_items:
            old = self._order.pop(0)
            self._items.pop(old, None)
        return iid

    def update(self, iid: str, *, percent=None, speed=None, line=None):
        item = self._items.get(iid)
        if not item or item["status"] != "running":
            return
        if percent is not None:
            item["percent"] = int(max(0, min(100, percent)))
        if speed is not None:
            item["speed"] = speed
        if line:
            line = line.strip("\r\n")
            if line:
                item["last_line"] = line
                item["lines"].append(line)
                if len(item["lines"]) > 60:
                    del item["lines"][:-60]

    def finish(self, iid: str, status: str, error=None):
        item = self._items.get(iid)
        if not item:
            return
        item["status"] = status
        item["percent"] = 100 if status == "done" else item["percent"]
        item["finished_at"] = time.time()
        item["error"] = error

    def snapshot(self):
        return [dict(self._items[i]) for i in self._order]

    def active_count(self):
        return sum(1 for i in self._order if self._items[i]["status"] == "running")

    def kill(self, iid: str) -> bool:
        item = self._items.get(iid)
        if not item or item["status"] != "running":
            return False
        pgid = item.get("pgid")
        if pgid:
            try:
                os.killpg(pgid, 9)
            except Exception:
                pass
        item["status"] = "canceled"
        item["finished_at"] = time.time()
        return True


manager = DownloadsManager()


def _download_cwd(command: str) -> str | None:
    """Téléchargements vers ~/Téléchargements sauf si la commande fixe déjà une sortie.
    Docker/K8s et git: ~ (le cwd courant de l'utilisateur, pas Téléchargements)."""
    if re.search(r"\b(docker|kubectl|helm|k3s|k9s)\b", command):
        return os.path.expanduser("~")
    if re.search(r"(?:-[oO]\s+[~/]|--output\s+[~/]|git\s+clone)", command):
        return os.path.expanduser("~")
    return _desc_dir


async def run_tracked(command: str, title: str | None = None,
                      kind: str | None = None, cwd: str | None = None,
                      timeout: float = 1800, stall_timeout: float = 60.0):
    """Exécute un transfert en streaming de sortie, met à jour le manager.
    Retourne (iid, status, tail_output)."""
    k = classify(command) if kind is None else (kind, "")
    if k is None:
        return (None, None, None)
    kind = kind or k[0]
    title = title or title_for(kind, command)
    iid = manager.start(kind, title, command)
    workdir = cwd or _download_cwd(command)
    os.makedirs(workdir, exist_ok=True)
    activity.log("cmd", f"{title} — {command}", source="terminal")

    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=workdir,
        start_new_session=True,
    )
    manager._items[iid]["pgid"] = proc.pid

    last_active = [time.monotonic()]

    async def pump(stream):
        buf = b""
        while True:
            data = await stream.read(1024)
            if not data:
                break
            buf += data
            last_active[0] = time.monotonic()
            # curl écrit la progression avec \r : scinder sur \r ET \n
            while buf:
                i = buf.find(b"\n")
                j = buf.find(b"\r")
                if i < 0 and j < 0:
                    break
                cut = (j if i < 0 else i) if j >= 0 else i
                if i >= 0 and j >= 0:
                    cut = min(i, j)
                frag = buf[:cut]
                buf = buf[cut + 1:]
                if frag:
                    text = frag.decode(errors="replace")
                    percent, speed = _parse_line(text)
                    manager.update(iid, percent=percent, speed=speed, line=text)

    stdout_p = asyncio.ensure_future(pump(proc.stdout))
    stderr_p = asyncio.ensure_future(pump(proc.stderr))
    reason = None

    async def monitor():
        while not (stdout_p.done() and stderr_p.done()):
            if stall_timeout and (time.monotonic() - last_active[0]) > stall_timeout:
                return "Aucun progrès (réseau bloqué ?)"
            await asyncio.sleep(1)

    try:
        stall_reason = await asyncio.wait_for(monitor(), timeout=timeout)
    except asyncio.TimeoutError:
        stall_reason = "Délai dépassé"
    reason = stall_reason
    if not reason and proc.returncode is None:
        reason = "Aucun progrès (réseau bloqué ?)"
    if reason:
        try:
            os.killpg(proc.pid, 9)
        except Exception:
            pass

    if reason:
        manager.finish(iid, "error", error=reason)
        activity.log("error", f"{title} → {reason}", source="terminal")
        tail = manager._items[iid]["lines"][-6:]
        for t in (stdout_p, stderr_p):
            try:
                await asyncio.wait_for(t, timeout=3)
            except Exception:
                pass
        return (iid, "error", f"Interrompu : {reason}.\n" + "\n".join(tail))

    rc = await proc.wait()
    status = "done" if rc == 0 else "error"
    if manager._items.get(iid, {}).get("status") == "canceled":
        status = "canceled"
    manager.finish(iid, status)
    activity.log("success" if status == "done" else "error",
                 f"{title} → {'terminé' if status == 'done' else 'échec'}", source="terminal")
    tail = manager._items[iid]["lines"][-12:]
    out = "\n".join(tail) if tail else f"(code {rc})"
    return (iid, status, out)