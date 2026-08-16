import os
import subprocess
import json
import difflib
import tempfile
from pathlib import Path

from . import tool

ALEX_ROOT = Path(__file__).resolve().parent.parent.parent

# ─── Backup pour rollback ───────────────────────────────────────────────────
_backups: dict[str, str] = {}

# ─── Journal des modifications de code (affiché dans le modal frontend) ─────
_code_log: list[dict] = []
_MAX_LOG = 50
_last_listener = None  # fonction async appelée après chaque write_code


def set_code_listener(fn):
    """Enregistre un callback (async) appelé après chaque modification de code."""
    global _last_listener
    _last_listener = fn


def _record_change(path: str, diff: str, ok: bool, old: str = None, new: str = None, lang: str = None):
    import time
    _code_log.append({
        "time": time.time(),
        "path": path,
        "diff": diff,
        "ok": ok,
        "old": old,
        "new": new,
        "lang": lang,
    })
    if len(_code_log) > _MAX_LOG:
        _code_log[: len(_code_log) - _MAX_LOG] = []


def _lang_from_path(path: str) -> str:
    """Devine le langage à partir de l'extension du fichier."""
    ext = os.path.splitext(path)[1].lstrip(".").lower()
    return {
        "py": "python", "pyw": "python",
        "js": "javascript", "jsx": "jsx", "ts": "typescript", "tsx": "tsx",
        "html": "html", "htm": "html",
        "css": "css", "scss": "scss",
        "json": "json",
        "md": "markdown", "markdown": "markdown",
        "sh": "bash", "bash": "bash",
        "yml": "yaml", "yaml": "yaml",
        "toml": "toml", "ini": "ini",
        "c": "c", "cpp": "cpp", "h": "c", "java": "java", "go": "go", "rs": "rust",
    }.get(ext, "")


def get_code_log(limit: int = 30) -> list[dict]:
    return list(_code_log[-limit:])


def record_chat_code(path: str, code: str, lang: str = "") -> dict:
    """Enregistre le code généré par Alex dans la discussion (modal) pour qu'elle
    garde en tête ce qu'elle a produit. Même journal que write_code."""
    import time
    _record_change(path, "", ok=True, old=None, new=code, lang=lang)
    ev = _code_log[-1]
    ev["source"] = "chat"
    return ev


@tool("lire_code",
      "📖 Lit le code source d'Alex. Spécifie le chemin relatif depuis la racine "
      "(ex: brain/main.py, brain/tools/network.py).")
def lire_code(path: str = "brain/main.py") -> str:
    full_path = ALEX_ROOT / path
    if not full_path.exists():
        paths = list(ALEX_ROOT.rglob(path))
        if paths:
            full_path = paths[0]
        else:
            return f"❌ Fichier introuvable : {path}"
    try:
        content = full_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        info = f"📖 {path} ({len(lines)} lignes, {full_path.stat().st_size / 1024:.1f} Ko)"
        # Retourne le contenu complet ou tronqué
        if len(lines) > 200:
            preview = "\n".join(lines[:50]) + "\n...\n" + "\n".join(lines[-50:])
            return f"{info}\n```python\n{preview}\n```"
        return f"{info}\n```python\n{content}\n```"
    except Exception as e:
        return f"❌ Erreur lecture : {e}"


@tool("write_code",
      "Modifie le code source. Le diff s'affiche automatiquement dans le modal Code. "
      "Spécifie le chemin, le texte à remplacer (old) et le nouveau texte (new). "
      "Pour créer un nouveau fichier, laisse old vide.",
      dangerous=True)
def write_code(path: str = "", old: str = "", new: str = "") -> str:
    if not path:
        return "Usage : write_code path=brain/main.py old=ancien_texte new=nouveau_texte"
    if not new:
        return "Le paramètre new ne peut pas être vide."
    
    # Nettoyer les guillemets du paramètre old
    if old in ('""', "''", '""', "''"):
        old = ""
    
    full_path = ALEX_ROOT / path
    if not full_path.exists():
        # Créer un nouveau fichier
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(new, encoding="utf-8")
            lang = _lang_from_path(path)
            _record_change(path, f"Nouveau fichier: {path}", ok=True, old=None, new=new, lang=lang)
            if _last_listener is not None:
                try:
                    _last_listener(path, f"Nouveau fichier: {path}", ok=True, old=None, new=new, lang=lang)
                except Exception:
                    pass
            return f"{path} créé. Voir le modal Code."
        except Exception as e:
            return f"Erreur création : {e}"
    
    try:
        content = full_path.read_text(encoding="utf-8")
        if old and old not in content:
            _record_change(path, f"old introuvable : {old[:60]}", ok=False)
            return f"Texte introuvable dans {path}"
        _backups[path] = content
        new_content = content.replace(old, new, 1) if old else new
        full_path.write_text(new_content, encoding="utf-8")
        diff = "\n".join(list(difflib.unified_diff(
            content.splitlines(), new_content.splitlines(),
            fromfile=path, tofile=path, lineterm=""
        ))[:30])
        lang = _lang_from_path(path)
        _record_change(path, diff, ok=True, old=content, new=new_content, lang=lang)
        if _last_listener is not None:
            try:
                _last_listener(path, diff, ok=True, old=content, new=new_content, lang=lang)
            except Exception:
                pass
        return f"{path} modifié. Voir le modal Code."
    except Exception as e:
        return f"Erreur écriture : {e}"


@tool("executer_test",
      "🧪 Exécute les tests ou vérifie la syntaxe d'un fichier Python d'Alex. "
      "Si aucun chemin spécifié, vérifie tout le projet.",
      dangerous=True)
def executer_test(path: str = "") -> str:
    if path:
        full_path = ALEX_ROOT / path
        if not full_path.exists():
            paths = list(ALEX_ROOT.rglob(path))
            if paths:
                full_path = paths[0]
            else:
                return f"❌ Fichier introuvable : {path}"
        # Vérification syntaxe Python
        result = subprocess.run(
            [ALEX_ROOT / "brain/.venv/bin/python3", "-m", "py_compile", str(full_path)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return f"✅ Syntaxe OK : {path}"
        return f"❌ Erreur syntaxe :\n{result.stderr[:500]}"

    # Vérification de tout le projet Python
    brain_dir = ALEX_ROOT / "brain"
    errors = []
    for pyfile in sorted(brain_dir.rglob("*.py")):
        rel = pyfile.relative_to(ALEX_ROOT)
        result = subprocess.run(
            [ALEX_ROOT / "brain/.venv/bin/python3", "-m", "py_compile", str(pyfile)],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            errors.append(f"❌ {rel}:\n{result.stderr[:200]}")

    if not errors:
        pycount = len(list(brain_dir.rglob("*.py")))
        return f"✅ Tous les {pycount} fichiers Python sont valides !"
    return "\n".join(errors[:5])


@tool("git_rollback",
      "↩️ Annule la dernière modification sur un fichier (restaure le backup).",
      dangerous=True)
def git_rollback(path: str = "") -> str:
    if not path:
        if not _backups:
            return "❌ Aucun backup disponible. Fais d'abord une modification avec write_code."
        paths = "\n".join(f"  • {p}" for p in _backups)
        return f"📋 Fichiers avec backup :\n{paths}\nUtilise git_rollback path=<fichier> pour restaurer."

    if path not in _backups:
        return f"❌ Aucun backup pour {path}. Vérifie avec git_rollback sans paramètre."
    full_path = ALEX_ROOT / path
    try:
        full_path.write_text(_backups[path], encoding="utf-8")
        del _backups[path]
        return f"✅ {path} restauré à la version précédente."
    except Exception as e:
        return f"❌ Erreur rollback : {e}"


@tool("chercher_code",
      "🔍 Cherche un motif dans le code source d'Alex (grep sur le projet).")
def chercher_code(motif: str = "") -> str:
    if not motif:
        return "❌ Usage : chercher_code motif=timeout"
    brain_dir = ALEX_ROOT / "brain"
    results = subprocess.run(
        ["grep", "-rn", motif, str(brain_dir), "--include=*.py"],
        capture_output=True, text=True, timeout=30
    )
    lines = [l for l in results.stdout.splitlines() if l.strip()][:30]
    if not lines:
        return f"🔍 Aucun résultat pour « {motif} » dans le code."
    return f"🔍 Résultats pour « {motif} » ({len(lines)} occ.) :\n" + "\n".join(lines[:20])


@tool("lister_code",
      "📂 Liste tous les fichiers source Python d'Alex avec leur taille.")
def lister_code() -> str:
    brain_dir = ALEX_ROOT / "brain"
    pyfiles = sorted(brain_dir.rglob("*.py"))
    lines = [f"📂 Code source d'Alex ({len(pyfiles)} fichiers) :"]
    total = 0
    for pf in pyfiles:
        rel = pf.relative_to(ALEX_ROOT)
        size = pf.stat().st_size
        total += size
        lines.append(f"  • {rel} ({size/1024:.1f} Ko)")
    lines.append(f"\nTotal : {total/1024:.1f} Ko")
    return "\n".join(lines)
