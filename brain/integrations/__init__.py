"""Système d'intégrations pour Alex — connexion aux applications externes."""
import json
import os
import base64
from typing import Any, Optional
from pathlib import Path
from .logos import APP_LOGOS, get_logo, get_svg, get_all_logos

# ─── Registry des intégrations ──────────────────────────────────────────────
_integrations: dict[str, dict] = {}
_credentials: dict[str, dict] = {}

# Chemin vers le fichier de credentials
_CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "credentials.json")


def _ensure_data_dir():
    """Crée le dossier data si nécessaire."""
    data_dir = os.path.dirname(_CREDENTIALS_FILE)
    os.makedirs(data_dir, exist_ok=True)


def _load_credentials():
    """Charge les credentials depuis le fichier."""
    global _credentials
    if os.path.exists(_CREDENTIALS_FILE):
        try:
            with open(_CREDENTIALS_FILE, "r") as f:
                _credentials = json.load(f)
        except Exception:
            _credentials = {}


def _save_credentials():
    """Sauvegarde les credentials dans le fichier."""
    _ensure_data_dir()
    with open(_CREDENTIALS_FILE, "w") as f:
        json.dump(_credentials, f, indent=2, ensure_ascii=False)


def _mask_token(token: str) -> str:
    """Masque un token pour l'affichage."""
    if len(token) <= 8:
        return "****"
    return token[:4] + "****" + token[-4:]


# ─── Définition des intégrations disponibles ────────────────────────────────

INTEGRATION_DEFS = {
    "slack": {
        "name": "Slack",
        "description": "Messagerie et notifications Slack",
        "icon": "💬",
        "color": "#4A154B",
        "auth_type": "bearer",
        "base_url": "https://slack.com/api",
        "actions": {
            "send_message": {
                "name": "Envoyer un message",
                "description": "Envoie un message dans un canal Slack",
                "params": {"channel": "string", "message": "string"},
            },
            "list_channels": {
                "name": "Lister les canaux",
                "description": "Liste les canaux disponibles",
                "params": {},
            },
            "get_user_info": {
                "name": "Info utilisateur",
                "description": "Récupère les infos d'un utilisateur",
                "params": {"user_id": "string"},
            },
        },
    },
    "github": {
        "name": "GitHub",
        "description": "Gestion de code et de projets",
        "icon": "🐙",
        "color": "#24292e",
        "auth_type": "bearer",
        "base_url": "https://api.github.com",
        "actions": {
            "list_repos": {
                "name": "Lister les repositories",
                "description": "Liste les repositories de l'utilisateur",
                "params": {},
            },
            "get_repo": {
                "name": "Détails repository",
                "description": "Récupère les infos d'un repository",
                "params": {"repo": "string"},
            },
            "create_issue": {
                "name": "Créer une issue",
                "description": "Crée une nouvelle issue",
                "params": {"repo": "string", "title": "string", "body": "string"},
            },
            "list_issues": {
                "name": "Lister les issues",
                "description": "Liste les issues d'un repository",
                "params": {"repo": "string"},
            },
        },
    },
    "notion": {
        "name": "Notion",
        "description": "Base de données et documentation",
        "icon": "📝",
        "color": "#000000",
        "auth_type": "bearer",
        "base_url": "https://api.notion.com/v1",
        "headers": {"Notion-Version": "2022-06-28"},
        "actions": {
            "query_database": {
                "name": "Interroger une base",
                "description": "Interroge une base de données Notion",
                "params": {"database_id": "string"},
            },
            "create_page": {
                "name": "Créer une page",
                "description": "Crée une nouvelle page",
                "params": {"parent_id": "string", "title": "string", "content": "string"},
            },
            "search": {
                "name": "Rechercher",
                "description": "Recherche dans Notion",
                "params": {"query": "string"},
            },
        },
    },
    "google_calendar": {
        "name": "Google Calendar",
        "description": "Calendrier et événements",
        "icon": "📅",
        "color": "#4285F4",
        "auth_type": "oauth2",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/calendar"],
        "base_url": "https://www.googleapis.com/calendar/v3",
        "actions": {
            "list_events": {
                "name": "Lister les événements",
                "description": "Liste les événements à venir",
                "params": {"days": "int"},
            },
            "create_event": {
                "name": "Créer un événement",
                "description": "Crée un nouvel événement",
                "params": {"title": "string", "start": "string", "end": "string", "description": "string"},
            },
        },
    },
    "gmail": {
        "name": "Gmail",
        "description": "Emails et notifications",
        "icon": "📧",
        "color": "#EA4335",
        "auth_type": "oauth2",
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "scopes": ["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"],
        "base_url": "https://gmail.googleapis.com/gmail/v1",
        "actions": {
            "send_email": {
                "name": "Envoyer un email",
                "description": "Envoie un email",
                "params": {"to": "string", "subject": "string", "body": "string"},
            },
            "list_emails": {
                "name": "Lister les emails",
                "description": "Liste les emails récents",
                "params": {"max_results": "int"},
            },
        },
    },
    "discord": {
        "name": "Discord",
        "description": "Messagerie et communautés",
        "icon": "🎮",
        "color": "#5865F2",
        "auth_type": "bearer",
        "base_url": "https://discord.com/api/v10",
        "actions": {
            "send_message": {
                "name": "Envoyer un message",
                "description": "Envoie un message dans un canal",
                "params": {"channel_id": "string", "message": "string"},
            },
            "list_guilds": {
                "name": "Lister les serveurs",
                "description": "Liste les serveurs de l'utilisateur",
                "params": {},
            },
        },
    },
    "spotify": {
        "name": "Spotify",
        "description": "Musique et playlists",
        "icon": "🎵",
        "color": "#1DB954",
        "auth_type": "oauth2",
        "auth_url": "https://accounts.spotify.com/authorize",
        "token_url": "https://accounts.spotify.com/api/token",
        "scopes": ["user-read-playback-state", "user-modify-playback-state", "playlist-read-private"],
        "base_url": "https://api.spotify.com/v1",
        "actions": {
            "get_playback": {
                "name": "Lecture en cours",
                "description": "Récupère la lecture en cours",
                "params": {},
            },
            "search_track": {
                "name": "Rechercher un titre",
                "description": "Recherche un titre",
                "params": {"query": "string"},
            },
            "play": {
                "name": "Lancer la lecture",
                "description": "Lance la lecture d'un titre ou playlist",
                "params": {"uri": "string"},
            },
        },
    },
    "openai": {
        "name": "OpenAI",
        "description": "API IA (GPT, DALL-E, etc.)",
        "icon": "🤖",
        "color": "#10A37F",
        "auth_type": "bearer",
        "base_url": "https://api.openai.com/v1",
        "actions": {
            "chat": {
                "name": "Chat GPT",
                "description": "Envoie un message à GPT",
                "params": {"model": "string", "message": "string"},
            },
            "generate_image": {
                "name": "Générer une image",
                "description": "Génère une image avec DALL-E",
                "params": {"prompt": "string"},
            },
        },
    },
    "telegram": {
        "name": "Telegram",
        "description": "Messagerie instantanée",
        "icon": "📱",
        "color": "#0088cc",
        "auth_type": "bearer",
        "base_url": "https://api.telegram.org",
        "actions": {
            "send_message": {
                "name": "Envoyer un message",
                "description": "Envoie un message Telegram",
                "params": {"chat_id": "string", "message": "string"},
            },
            "get_updates": {
                "name": "Récupérer les messages",
                "description": "Récupère les derniers messages",
                "params": {},
            },
        },
    },
}


def register_integration(name: str, config: dict):
    """Enregistre une intégration."""
    _integrations[name] = config


def get_integration(name: str) -> Optional[dict]:
    """Récupère une intégration."""
    return _integrations.get(name)


def list_integrations() -> list[dict]:
    """Liste toutes les intégrations disponibles."""
    result = []
    for name, config in INTEGRATION_DEFS.items():
        has_cred = name in _credentials
        result.append({
            "name": name,
            "name_display": config["name"],
            "description": config["description"],
            "icon": config["icon"],
            "color": config["color"],
            "connected": has_cred,
            "actions": list(config.get("actions", {}).keys()),
        })
    return result


def get_integration_details(name: str) -> Optional[dict]:
    """Récupère les détails d'une intégration."""
    config = INTEGRATION_DEFS.get(name)
    if not config:
        return None
    has_cred = name in _credentials
    cred_info = {}
    if has_cred:
        cred = _credentials[name]
        if "token" in cred:
            cred_info["token_masked"] = _mask_token(cred["token"])
        if "client_id" in cred:
            cred_info["client_id"] = cred["client_id"]
    return {
        "name": name,
        "name_display": config["name"],
        "description": config["description"],
        "icon": config["icon"],
        "color": config["color"],
        "connected": has_cred,
        "credentials": cred_info,
        "actions": config.get("actions", {}),
    }


# ─── Gestion des credentials ───────────────────────────────────────────────

def save_credential(name: str, data: dict):
    """Sauvegarde les credentials d'une intégration."""
    _credentials[name] = data
    _save_credentials()
    print(f"[integrations] Credential sauvegardé: {name}")


def get_credential(name: str) -> Optional[dict]:
    """Récupère les credentials d'une intégration."""
    return _credentials.get(name)


def delete_credential(name: str):
    """Supprime les credentials d'une intégration."""
    _credentials.pop(name, None)
    _save_credentials()
    print(f"[integrations] Credential supprimé: {name}")


# ─── Exécution des actions ─────────────────────────────────────────────────

async def execute_action(integration_name: str, action_name: str, params: dict) -> str:
    """Exécute une action sur une intégration."""
    import httpx

    config = INTEGRATION_DEFS.get(integration_name)
    if not config:
        return f"Intégration inconnue: {integration_name}"

    action = config.get("actions", {}).get(action_name)
    if not action:
        return f"Action inconnue: {action_name} pour {integration_name}"

    cred = _credentials.get(integration_name)
    if not cred:
        return f"Intégration {integration_name} non configurée. Va dans les settings pour la connecter."

    base_url = config.get("base_url", "")
    headers = config.get("headers", {}).copy()

    # Auth
    auth_type = config.get("auth_type", "bearer")
    if auth_type == "bearer" and "token" in cred:
        headers["Authorization"] = f"Bearer {cred['token']}"
    elif auth_type == "oauth2" and "access_token" in cred:
        headers["Authorization"] = f"Bearer {cred['access_token']}"

    # Construire la requête
    url = f"{base_url}/{action_name.replace('_', '/')}"
    method = "GET"
    body = None

    # Logique par intégration
    if integration_name == "slack":
        if action_name == "send_message":
            url = f"{base_url}/chat.postMessage"
            method = "POST"
            body = {"channel": params.get("channel", ""), "text": params.get("message", "")}
        elif action_name == "list_channels":
            url = f"{base_url}/conversations.list"
        elif action_name == "get_user_info":
            url = f"{base_url}/users.info?user={params.get('user_id', '')}"

    elif integration_name == "github":
        url = f"{base_url}"
        if action_name == "list_repos":
            url = f"{base_url}/user/repos"
        elif action_name == "get_repo":
            url = f"{base_url}/repos/{params.get('repo', '')}"
        elif action_name == "create_issue":
            url = f"{base_url}/repos/{params.get('repo', '')}/issues"
            method = "POST"
            body = {"title": params.get("title", ""), "body": params.get("body", "")}
        elif action_name == "list_issues":
            url = f"{base_url}/repos/{params.get('repo', '')}/issues"

    elif integration_name == "notion":
        if action_name == "query_database":
            url = f"{base_url}/databases/{params.get('database_id', '')}/query"
            method = "POST"
            body = {}
        elif action_name == "create_page":
            url = f"{base_url}/pages"
            method = "POST"
            body = {
                "parent": {"database_id": params.get("parent_id", "")},
                "properties": {"title": {"title": [{"text": {"content": params.get("title", "")}}]}},
            }
        elif action_name == "search":
            url = f"{base_url}/search"
            method = "POST"
            body = {"query": params.get("query", "")}

    elif integration_name == "gmail":
        if action_name == "send_email":
            import base64 as b64
            message = f"To: {params.get('to', '')}\nSubject: {params.get('subject', '')}\n\n{params.get('body', '')}"
            raw = b64.urlsafe_b64encode(message.encode()).decode()
            url = f"{base_url}/users/me/messages/send"
            method = "POST"
            body = {"raw": raw}
        elif action_name == "list_emails":
            url = f"{base_url}/users/me/messages?maxResults={params.get('max_results', 10)}"

    elif integration_name == "discord":
        if action_name == "send_message":
            url = f"{base_url}/channels/{params.get('channel_id', '')}/messages"
            method = "POST"
            body = {"content": params.get("message", "")}
        elif action_name == "list_guilds":
            url = f"{base_url}/users/@me/guilds"

    elif integration_name == "spotify":
        if action_name == "get_playback":
            url = f"{base_url}/me/player"
        elif action_name == "search_track":
            url = f"{base_url}/search?q={params.get('query', '')}&type=track"
        elif action_name == "play":
            url = f"{base_url}/me/player/play"
            method = "PUT"
            body = {"uris": [params.get("uri", "")]}

    elif integration_name == "telegram":
        token = cred.get("token", "")
        if action_name == "send_message":
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            method = "POST"
            body = {"chat_id": params.get("chat_id", ""), "text": params.get("message", "")}
        elif action_name == "get_updates":
            url = f"https://api.telegram.org/bot{token}/getUpdates"

    # Exécuter la requête
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "POST":
                resp = await client.post(url, headers=headers, json=body)
            elif method == "PUT":
                resp = await client.put(url, headers=headers, json=body)
            else:
                return f"Méthode non supportée: {method}"

            if resp.status_code >= 400:
                return f"Erreur HTTP {resp.status_code}: {resp.text[:200]}"

            try:
                data = resp.json()
                return json.dumps(data, indent=2, ensure_ascii=False)[:2000]
            except Exception:
                return resp.text[:2000]

    except httpx.TimeoutException:
        return f"Timeout lors de l'appel à {integration_name}"
    except Exception as e:
        return f"Erreur: {e}"


# ─── Outils pour le LLM ───────────────────────────────────────────────────

def get_integration_tools() -> list[dict]:
    """Retourne les outils d'intégration pour le LLM."""
    tools = []
    for name, config in INTEGRATION_DEFS.items():
        if name not in _credentials:
            continue  # Skip les intégrations non configurées
        for action_id, action in config.get("actions", {}).items():
            tools.append({
                "name": f"integration_{name}_{action_id}",
                "description": f"[{config['name']}] {action['name']}: {action['description']}",
                "parameters": action.get("params", {}),
            })
    return tools


# Charger les credentials au démarrage
_load_credentials()
