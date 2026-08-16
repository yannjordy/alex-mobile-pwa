"""
Routeur intelligent : fait correspondre une requête à un outil via des motifs
sans passer par le LLM. Solution 100% locale, instantanée.
"""
import re
import subprocess
from typing import Optional

from . import tools as tools_registry


# ─── Helpers ────────────────────────────────────────────────────────────────
def _extract_path(msg: str, default: str = "") -> str:
    # Pour la météo : extraire le lieu après "à", "a", "pour", "de"
    # Gérer les cas multiples comme "Paris et Yaoundé" → prendre le premier lieu
    meteo_match = re.search(r'(?:à|a|pour|de|sur)\s+([A-ZÀ-Úa-zàú][\w\s\-]+?)(?:\s*[?.!]|\s*$)', msg)
    if meteo_match:
        lieu = meteo_match.group(1).strip()
        # Si le lieu contient "et" ou ",", prendre seulement le premier lieu
        if " et " in lieu:
            lieu = lieu.split(" et ")[0].strip()
        if "," in lieu:
            lieu = lieu.split(",")[0].strip()
        return lieu
    m = re.search(r'(?:dans|sur|de|le\s+dossier|le\s+répertoire)\s+(.+?)(?:\s*$|\s+et\s)', msg)
    if m:
        return m.group(1).strip()
    m = re.search(r'(?:^|[\s/])(/[\w/\.\-~]+)', msg)
    if m:
        return m.group(1)
    m = re.search(r'(?:dans|sur|/)\s*([\w/\.\-~]+)', msg)
    if m:
        return m.group(1).strip("/")
    # Fallback : dernier mot après les préfixes connus
    for prefix in ("météo", "meteo", "temps", "prévisions", "dossier", "fichier"):
        if prefix in msg.lower():
            after = msg.lower().split(prefix, 1)[-1].strip().lstrip(" :\"'")
            if after:
                words = after.split()
                return words[0] if words else default
    return default


def _extract_text(msg: str, default: str = "") -> str:
    for prefix in ("traduis", "traduit", "translate", "dis", "dit",
                   "raconte", "joue", "lance", "ouvre"):
        if prefix in msg:
            idx = msg.index(prefix) + len(prefix)
            return msg[idx:].strip().lstrip(" -:\"'").strip()
    return default


def _extract_count(msg: str, default: int = 10) -> int:
    m = re.search(r'(\d+)\s*(?:processus?|lignes?|fichiers?|résultats?)', msg)
    return min(int(m.group(1)), 100) if m else default


def _extract_query(msg: str) -> str:
    for prefix in ("cherche dans le code", "cherche dans brain",
                   "cherche sur google", "cherche sur internet",
                   "cherche sur le web", "cherche dans le source",
                   "cherche dans", "recherche sur internet",
                   "montre moi une image", "montre moi des images",
                   "affiche une image", "donne moi une image",
                   "montre moi une photo", "montre photo",
                   "montre moi une vidéo", "montre moi une video",
                   "montre vidéo", "montre video",
                   "cherche une image", "cherche image",
                   "trouve image", "image de",
                   "cherche une vidéo", "cherche vidéo",
                   "trouve vidéo", "vidéo de", "video de",
                   "une image de", "des images de",
                   "une photo de", "une vidéo de",
                   "cherche", "recherche", "trouve", "google",
                   "calcule", "calcul", "calcule moi", "combien fait",
                   "combien font", "additionne", "soustrais",
                   "multiplie", "divise"):
        idx = msg.lower().find(prefix)
        if idx >= 0:
            after = msg[idx + len(prefix):].strip().lstrip(" :\"'")
            if after and not after.startswith(prefix):
                return after
    return msg


def _extract_time(msg: str, default: str = "") -> str:
    """Extrait une heure du message (HH:MM ou 'dans X minutes')."""
    # Chercher HH:MM
    m = re.search(r'(\d{1,2})[hH:](\d{2})', msg)
    if m:
        return f"{int(m.group(1)):02d}:{m.group(2)}"
    
    # Chercher "dans X minutes"
    m = re.search(r'dans\s+(\d+)\s*(?:min|minutes?|mn)', msg, re.IGNORECASE)
    if m:
        return f"dans {m.group(1)} minutes"
    
    # Chercher "dans X heures"
    m = re.search(r'dans\s+(\d+)\s*(?:h|heures?)', msg, re.IGNORECASE)
    if m:
        return f"dans {m.group(1)} heures"
    
    return default


def _extract_task_type(msg: str, default: str = "notify") -> str:
    """Extrait le type de tâche du message."""
    msg_lower = msg.lower()
    
    if any(word in msg_lower for word in ["fond d'écran", "fond ecran", "wallpaper", "image"]):
        return "wallpaper"
    elif any(word in msg_lower for word in ["bluetooth", "ble"]):
        return "bluetooth"
    elif any(word in msg_lower for word in ["application", "app", "lance", "ouvre"]):
        return "app"
    elif any(word in msg_lower for word in ["volume", "son"]):
        return "volume"
    elif any(word in msg_lower for word in ["luminosité", "luminosite", "éclairage"]):
        return "brightness"
    elif any(word in msg_lower for word in ["commande", "script", "exécute"]):
        return "command"
    elif any(word in msg_lower for word in ["notification", "notifie", "alerte"]):
        return "notify"
    
    return default


def _extract_task_label(msg: str, default: str = "") -> str:
    """Extrait un label/description de la tâche."""
    # Pour les rappels, prendre tout le message après "rappelle moi" ou similaire
    for prefix in ["rappelle moi", "me rappeler", "rappele moi", "rappel"]:
        idx = msg.lower().find(prefix)
        if idx >= 0:
            return msg[idx + len(prefix):].strip().lstrip(" :\"'")
    
    # Pour les tâches, prendre la partie descriptive
    for prefix in ["pour", "de", "à", "a"]:
        idx = msg.lower().find(prefix)
        if idx >= 0:
            after = msg[idx + len(prefix):].strip().lstrip(" :\"'")
            if len(after) > 5:  # Assez long pour être un label
                return after[:50]  # Limiter la longueur
    
    return default


# ─── Inline tools (pas d'outil dédié dans le registre) ─────────────────────

def _calculer(expression: str) -> str:
    """Évalue une expression mathématique simple en toute sécurité."""
    expr = expression.strip().replace("×", "*").replace("÷", "/").replace("x", "*")
    if not re.match(r'^[\d\s\+\-\*\/\(\)\.\,%]+$', expr):
        return "❌ Expression invalide. Utilise des chiffres et + - * / ( ) ."
    try:
        expr = expr.replace(",", ".")
        result = eval(expr, {"__builtins__": {}}, {})
        return f"🧮 {expression} = {result}"
    except Exception as e:
        return f"❌ Erreur de calcul : {e}"


def _traduire(texte: str) -> str:
    """Traduction simple via dictionnaire intégré."""
    # Nettoie le texte : enlève "en français", "vers le français", etc.
    for suffix in (" en français", " vers le français", " en anglais",
                   " vers l'anglais", " en espagnol", " vers l'espagnol",
                   " en allemand", " en italien", "french", "english"):
        if texte.lower().endswith(suffix):
            texte = texte[:-len(suffix)].strip()
    dico = {
        "hello world": "bonjour le monde",
        "hello": "bonjour",
        "world": "monde",
        "good morning": "bonjour",
        "good evening": "bonsoir",
        "good night": "bonne nuit",
        "thank you": "merci",
        "thanks": "merci",
        "please": "s'il vous plaît",
        "sorry": "désolé",
        "yes": "oui",
        "no": "non",
        "maybe": "peut-être",
        "friend": "ami",
        "love": "amour",
        "time": "temps",
        "day": "jour",
        "night": "nuit",
        "water": "eau",
        "food": "nourriture",
        "house": "maison",
        "car": "voiture",
        "computer": "ordinateur",
        "phone": "téléphone",
        "dog": "chien",
        "cat": "chat",
    }
    t = texte.lower().strip()
    if t in dico:
        return f"🌐 {texte} → {dico[t]}"
    result = subprocess.run(
        ["which", "trans"], capture_output=True, text=True, timeout=5
    )
    if result.returncode == 0:
        out = subprocess.run(
            ["trans", "-b", f":fr", texte],
            capture_output=True, text=True, timeout=10
        )
        if out.returncode == 0 and out.stdout.strip():
            return f"🌐 {texte} → {out.stdout.strip()}"
    # Fallback : explication basique
    return f"🌐 Je ne peux pas traduire « {texte} » pour l'instant. Essaie avec un outil externe."


# ─── Routes ─────────────────────────────────────────────────────────────────
ROUTES: list[tuple[tuple[str, ...], str, callable, bool]] = []

def route(keywords: tuple[str, ...], tool_name: str, param_fn=None, dangerous: bool = False):
    ROUTES.append((keywords, tool_name, param_fn, dangerous))


# --- Tâches programmées / Scheduler ---
route(("programme", "planifie", "programme pour", "planifie pour"),
      "tache_programmee", lambda m, p: {"action": "add", "time": _extract_time(m), "task_type": _extract_task_type(m), "label": _extract_task_label(m)})
route(("tâche programmée", "tache programmee", "liste des tâches", "mes tâches",
       "tâches en cours", "planifier"),
      "tache_programmee", lambda m, p: {"action": "list"})
route(("supprime la tâche", "supprime tâche", "supprimer tâche", "supprimer la tâche",
       "efface la tâche", "effacer tâche"),
      "tache_programmee", lambda m, p: {"action": "remove", "label": _extract_task_label(m)})
route(("rappel", "rappelle moi", "me rappeler", "rappele moi"),
      "rappel_intelligent", lambda m, p: {"time": _extract_time(m), "message": _extract_task_label(m)})

# --- Fichiers ---
route(("liste les fichiers", "liste les dossiers", "ls", "affiche les fichiers",
       "contenu du dossier", "que contient", "quels fichiers", "contient le dossier",
       "fichiers dans", "dossiers dans", "voir le dossier"),
      "lister_dossier", lambda m, p: {"path": _extract_path(m, ".")})
route(("lit le fichier", "lis le fichier", "ouvre le fichier", "affiche le fichier",
       "montre le fichier", "cat", "affiche le contenu"),
      "lire_fichier", lambda m, p: {"path": _extract_path(m, ".")})
route(("cherche des fichiers", "trouve des fichiers", "cherche fichier",
       "cherche un fichier", "recherche fichier", "chercher fichier"),
      "rechercher_fichiers", lambda m, p: {"pattern": _extract_query(m) or "*", "path": "."})
route(("crée un dossier", "crée un répertoire", "nouveau dossier", "mkdir"),
      "creer_dossier", lambda m, p: {"path": _extract_path(m, ".")})
route(("supprime un fichier", "supprime fichier", "supprimer un fichier", "supprimer fichier",
       "efface un fichier", "effacer fichier"),
      "supprimer_fichier", None, dangerous=True)
route(("copie", "copier", "duplique"), "copier_fichier", None, dangerous=True)

# --- Code / Auto-programmation ---
route(("lis le code", "lis le source", "lis brain", "affiche le code",
       "montre le code", "ouvre le code", "lit le code", "lit brain",
       "affiche brain"),
      "lire_code", lambda m, p: {"path": _extract_path(m, "brain/main.py")})
route(("modifie le code", "modifie brain", "change le code", "change brain",
       "écris dans brain", "écris dans le code", "modifie", "édite"),
      "write_code", None, dangerous=True)
route(("teste le code", "teste brain", "vérifie le code", "vérifie brain",
       "test syntaxe", "vérifie syntaxe"),
      "executer_test", lambda m, p: {"path": _extract_path(m, "")}, dangerous=True)
route(("rollback", "annule la modif", "annule le changement",
       "restaure", "reviens en arrière", "undo", "annule modif"),
      "git_rollback", lambda m, p: {"path": _extract_path(m, "")}, dangerous=True)
route(("cherche dans le code", "cherche dans brain", "cherche dans le source",
       "cherche code", "grep", "cherche dans brain"),
      "chercher_code", lambda m, p: {"motif": _extract_query(m)})
route(("liste les fichiers source", "liste les fichiers python", "liste le code",
       "quels fichiers python", "structure du projet", "voir les sources"),
      "lister_code")

# --- Système ---
route(("info système", "informations système", "infos système",
       "état du système", "status système", "mon système",
       "ressources", "cpu", "mémoire", "ram", "disque", "stockage",
       "utilisation", "charge"),
      "info_systeme")
route(("processus", "process", "programme en cours",
       "que tourne", "applications ouvertes", "programmes ouverts"),
      "processus", lambda m, p: {"count": _extract_count(m, 20)})
route(("batterie", "battery", "charge", "autonomie"),
      "batterie")

# --- CLI / Commandes terminal ---
route(("exécute", "execute", "exécute la commande", "execute la commande",
       "lance la commande", "tape la commande", "fais la commande",
       "exécute cette commande", "run cette commande"),
      "commande",
      lambda m, p: {"command": _extract_query(m).strip("`").strip()}, dangerous=True)

# --- Réseau / WiFi / BLE ---
route(("scan wifi", "wifi scan", "réseaux wifi", "voir les wifi",
       "liste les wifi", "réseaux disponibles", "wifi dispo",
       "vois les wifi"),
      "wifi_scan")
route(("wifi status", "état wifi", "connexion wifi", "mon wifi",
       "ip", "adresse ip", "config réseau", "network config",
       "mon ip", "config ip", "status réseau", "connecté au wifi",
       "mon réseau", "mon ip", "quel wifi", "status wifi"),
      "wifi_status")
route(("connecte toi au wifi", "connecte au wifi", "wifi connect",
       "connecte moi au wifi", "rejoins le wifi", "rejoins le réseau",
       "connecte à"),
      "wifi_connect",
      lambda m, p: {"ssid": m.split("wifi")[-1].strip().lstrip(" :\"'").split()[0] if "wifi" in m
                    else m.split("réseau")[-1].strip().lstrip(" :\"'").split()[0] if "réseau" in m
                    else m.split("à")[-1].strip().lstrip(" :\"'").split()[0] if "à" in m
                    else "",
                    "password": ""}, dangerous=True)
route(("wifi monitor", "monitor wifi", "écouter wifi", "sniff wifi",
       "analyse wifi", "wifi analyse", "surveiller wifi"),
      "wifi_monitor", dangerous=True)
route(("wifi test", "teste wifi", "test sécurité wifi",
       "crack wifi", "casser wifi", "pirater wifi"),
      "wifi_security_test", dangerous=True)
route(("scan ble", "ble scan", "bluetooth scan", "scanne bluetooth",
       "appareils bluetooth", "voir les bluetooth", "ble liste"),
      "ble_scan")
route(("track ble", "ble tracker", "suivre bluetooth", "tracker"),
      "ble_tracker", lambda m, p: {"mac": "?"}, dangerous=True)

# --- Web / Recherche ---
route(("cherche sur google", "cherche sur internet", "google",
       "cherche sur le web", "recherche sur internet",
       "trouve sur internet", "cherche google"),
      "recherche_web", lambda m, p: {"requete": _extract_query(m)})
route(("cherche une image", "cherche image", "trouve image", "image de",
       "montre moi une image", "montre moi des images", "affiche une image",
       "donne moi une image", "image", "photo", "photo de", "montre photo",
       "montre moi une photo", "des images de", "une photo de"),
      "recherche_image", lambda m, p: {"requete": _extract_query(m).removeprefix("une image ").removeprefix("image ").removeprefix("une photo ").removeprefix("photo ").strip()})
route(("cherche une vidéo", "cherche vidéo", "cherche video",
       "trouve vidéo", "trouve video", "montre moi une vidéo",
       "montre moi une video", "vidéo de", "video de", "montre vidéo"),
      "recherche_video", lambda m, p: {"requete": _extract_query(m)})

# --- Météo ---
route(("météo", "meteo", "temps", "quel temps", "temps qu'il fait",
       "temps il fait", "prévisions"),
      "meteo", lambda m, p: {"lieu": _extract_path(m, "")})

# --- Utilitaires (inline) ---
route(("traduis", "traduit", "traduction", "translate"),
      "__inline_translate__", lambda m, p: {"texte": _extract_text(m)})
route(("calcule moi", "combien fait", "combien font",
       "additionne", "soustrais", "multiplie", "divise"),
      "__inline_calc__", lambda m, p: {"expression": _extract_query(m)})
route(("mcp liste", "mcp list", "liste des mcp", "extensions mcp",
       "plugins disponibles", "liste mcp"),
      "mcp_list")
route(("github", "github mcp"), "github_mcp",
      lambda m, p: {"action": "search_code", "query": _extract_query(m)})

# --- Bureau ---
route(("volume +", "volume plus", "monte le son", "augmente le volume", "son plus"),
      "volume", lambda m, p: {"action": "up", "valeur": "10%"})
route(("volume -", "volume moins", "baisse le son", "diminue le volume", "son moins"),
      "volume", lambda m, p: {"action": "down", "valeur": "10%"})
route(("mute", "silence", "coupe le son", "son off", "sourdine"),
      "volume", lambda m, p: {"action": "mute"})
route(("luminosité +", "luminosité plus", "éclaire", "plus clair", "lumière plus"),
      "luminosite", lambda m, p: {"niveau": "+10"})
route(("luminosité -", "luminosité moins", "moins clair", "assombrit", "lumière moins"),
      "luminosite", lambda m, p: {"niveau": "-10"})

# --- Sites web ---
route(("créer un site web", "creer un site web", "site web", "créer site",
       "faire un site web", "faire site", "portfolio", "créer portfolio",
       "créer un portfolio", "landing page", "créer une landing"),
      "creer_site_web", lambda m, p: {"nom": _extract_query(m).replace("créer un site web ", "").replace("creer un site web ", "").strip() or "mon-site", "type": "portfolio"})
route(("lancer serveur dev", "lancer serveur", "serveur local", "lancer le serveur"),
      "lancer_serveur_dev", lambda m, p: {"dossier": _extract_query(m) or "."})

# --- Tâches programmées / Scheduler ---
route(("programme", "planifie", "programme pour", "planifie pour"),
      "tache_programmee", lambda m, p: {"action": "add", "time": _extract_time(m), "task_type": _extract_task_type(m), "label": _extract_task_label(m)})
route(("tâche programmée", "tache programmee", "liste des tâches", "mes tâches",
       "tâches en cours", "planifier"),
      "tache_programmee", lambda m, p: {"action": "list"})
route(("supprime la tâche", "supprime tâche", "supprimer tâche", "supprimer la tâche",
       "efface la tâche", "effacer tâche"),
      "tache_programmee", lambda m, p: {"action": "remove", "label": _extract_task_label(m)})
route(("rappel", "rappelle moi", "me rappeler", "rappele moi"),
      "rappel_intelligent", lambda m, p: {"time": _extract_time(m), "message": _extract_task_label(m)})

# --- Danger confirmation (mots entiers uniquement pour éviter "oui" dans "quoi") ---
route(("confirme", "valide", "vas-y", "go", "d'accord"),
      "__confirm_yes__", lambda m, p: {})
route(("annule", "stop", "cancel", "arrête", "pas maintenant"),
      "__confirm_no__", lambda m, p: {})


# ─── Moteur de routage ──────────────────────────────────────────────────────

def route_message(message: str) -> Optional[dict]:
    msg = message.lower().strip()
    words = set(msg.split())
    
    # Détecter les requêtes multi-parties (avec "puis", "ensuite", "et après")
    if any(separator in msg for separator in [" puis ", " ensuite ", " et après ", " et puis "]):
        # Pour les requêtes multi-parties, on ne route pas directement
        # On laisse opencode gérer la complexité
        return None
    
    # Cas spécial : "calcule <expression math>" seul mot déclencheur
    # Vérifier qu'il y a une vraie expression mathématique après "calcule"
    if msg.startswith("calcule") or " calcule " in msg:
        remainder = re.sub(r'^.*calcule\s*', '', msg).strip()
        if re.search(r'\d\s*[\+\-\*\/×÷]', remainder) or re.fullmatch(r'[\d\s\+\-\*\/\(\)\.\,%]+', remainder):
            return {"tool": "__inline_calc__", "params": {"expression": remainder}}

    for keywords, tool_name, param_fn, dangerous in ROUTES:
        for kw in keywords:
            kw_lower = kw.lower()
            if " " in kw_lower:
                # Phrase multi-mots : substring match (mais éviter les faux positifs courts)
                if kw_lower in msg:
                    params = param_fn(message, {}) if param_fn else {}
                    return {"tool": tool_name, "params": params}
            elif kw_lower in words:
                # Mot simple : match exact (mot entier)
                params = param_fn(message, {}) if param_fn else {}
                return {"tool": tool_name, "params": params}
    return None


async def execute_direct(message: str) -> Optional[str]:
    route = route_message(message)
    if not route:
        return None

    tool_name = route["tool"]
    params = route["params"]

    # Inline tools
    if tool_name == "__inline_calc__":
        return _calculer(params.get("expression", ""))
    if tool_name == "__inline_translate__":
        return _traduire(params.get("texte", ""))

    # Confirmation
    if tool_name == "__confirm_yes__":
        return "CONFIRM_YES"
    if tool_name == "__confirm_no__":
        return "CONFIRM_NO"

    # Real tool execution
    try:
        result = await tools_registry.execute(tool_name, params)
        if result:
            return f"{result}"
        return f"❌ L'outil {tool_name} n'a retourné aucun résultat."
    except Exception as e:
        return f"❌ Erreur {tool_name} : {e}"
