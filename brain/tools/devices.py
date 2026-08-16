import os
import subprocess
from pathlib import Path

from . import tool

_CAPTURE_DIR = Path.home() / "Documents" / "alex-assistant" / ".captures"


def _served_url(path: Path) -> str:
    """Construit l'URL servie par le brain pour le fichier capturé."""
    from urllib.parse import quote
    return f"http://127.0.0.1:8765/file?path={quote(str(path))}"


def _pick_device() -> str:
    """Retourne le 1er /dev/video* disponible."""
    for v in sorted(Path("/dev").glob("video*")):
        return str(v)
    return "/dev/video0"


@tool("capturer_webcam", "Prend une photo avec la webcam. Privé : nécessite une validation utilisateur.")
def capture_webcam() -> str:
    """Prend une photo avec la webcam et envoie l'URL de l'image servie.

    Args:
        (aucun paramètre)
    """
    _CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = _CAPTURE_DIR / f"capture_{int(__import__('time').time())}.jpg"
    dev = _pick_device()
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "v4l2", "-video_size", "640x480", "-i", dev,
             "-frames:v", "1", str(out)],
            capture_output=True, text=True, timeout=20,
        )
        if r.returncode != 0 or not out.exists():
            return f"Échec de la capture webcam : {r.stderr[-300:] if r.stderr else 'sortie vide'}"
    except FileNotFoundError:
        return "ffmpeg est requis pour la webcam. Installe-le avec : sudo apt install ffmpeg"
    except Exception as e:
        return f"Erreur capture webcam : {e}"
    return _served_url(out)


@tool("capturer_ecran", "Capture l'écran du bureau. Privé : nécessite une validation utilisateur.")
def capture_screen() -> str:
    """Capture l'écran du bureau et envoie l'URL de l'image servie.

    Args:
        (aucun paramètre)
    """
    _CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    out = _CAPTURE_DIR / f"ecran_{int(__import__('time').time())}.png"

    # 1) ImageMagick import (session X)
    try:
        r = subprocess.run(
            ["import", "-window", "root", str(out)],
            capture_output=True, text=True, timeout=12,
            env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0")},
        )
        if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
            return _served_url(out)
    except Exception:
        pass

    # 2) GNOME Shell screenshot (Wayland)
    try:
        r = subprocess.run(
            ["gdbus", "call", "--session", "--dest", "org.gnome.Shell",
             "--object-path", "/org/gnome/Shell/Screenshot",
             "--method", "org.gnome.Shell.Screenshot.Screenshot",
             str(out), "true", "true", "false"],
            capture_output=True, text=True, timeout=12,
        )
        if "true" in r.stdout and out.exists() and out.stat().st_size > 0:
            return _served_url(out)
    except Exception:
        pass

    return "Capture d'écran indisponible : session graphique verrouillée ou outil manquant."


@tool("ouvrir_webcam", "Envoie l'aide pour ouvrir la webcam en aperçu direct.")
def open_webcam() -> str:
    """Indique comment ouvrir un aperçu direct de la webcam.

    Args:
        (aucun paramètre)
    """
    return ("Aperçu webcam : `ffplay -f v4l2 /dev/video0` (terminal), ou capture d'une "
            "photo via « regarde-moi ». Dis-moi si tu préfères que je te prenne en photo. "
            "📸 Tout reste local.")