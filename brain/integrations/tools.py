"""Outils d'intégration pour Alex — exécution via le LLM."""
from ..tools import tool
from . import (
    list_integrations, get_integration_details, execute_action,
    save_credential, get_credential, delete_credential, INTEGRATION_DEFS,
)


@tool("integrations_list", "Liste les intégrations disponibles et leur statut")
async def integrations_list() -> str:
    """Liste toutes les intégrations disponibles."""
    integrations = list_integrations()
    lines = ["🔌 Intégrations disponibles:\n"]
    for integ in integrations:
        status = "✅ Connecté" if integ["connected"] else "❌ Non connecté"
        lines.append(f"  {integ['icon']} **{integ['name_display']}** — {status}")
        lines.append(f"     {integ['description']}")
        if integ["connected"]:
            lines.append(f"     Actions: {', '.join(integ['actions'])}")
        lines.append("")
    return "\n".join(lines)


@tool("integrations_info", "Détails d'une intégration spécifique")
async def integrations_info(name: str) -> str:
    """Récupère les détails d'une intégration."""
    details = get_integration_details(name)
    if not details:
        return f"❌ Intégration inconnue: {name}\nIntégrations disponibles: {', '.join(INTEGRATION_DEFS.keys())}"

    lines = [f"{details['icon']} **{details['name_display']}**\n"]
    lines.append(f"Description: {details['description']}")
    lines.append(f"Statut: {'✅ Connecté' if details['connected'] else '❌ Non connecté'}")

    if details["connected"] and details.get("credentials"):
        lines.append(f"\nCredentials:")
        for k, v in details["credentials"].items():
            lines.append(f"  - {k}: {v}")

    if details.get("actions"):
        lines.append(f"\nActions disponibles:")
        for action_id, action in details["actions"].items():
            params = ", ".join(action.get("params", {}).keys()) or "aucun"
            lines.append(f"  - **{action_id}**: {action['name']} (params: {params})")

    return "\n".join(lines)


@tool("integrations_connect", "Connecte une intégration avec un token API")
async def integrations_connect(name: str, token: str = "", client_id: str = "", client_secret: str = "") -> str:
    """Connecte une intégration avec des credentials."""
    if name not in INTEGRATION_DEFS:
        return f"❌ Intégration inconnue: {name}\nIntégrations disponibles: {', '.join(INTEGRATION_DEFS.keys())}"

    config = INTEGRATION_DEFS[name]
    cred_data = {}

    if config.get("auth_type") == "bearer":
        if not token:
            return f"❌ Token requis pour {name}. Utilise: integrations_connect(name='{name}', token='ton_token')"
        cred_data["token"] = token
    elif config.get("auth_type") == "oauth2":
        if client_id and client_secret:
            cred_data["client_id"] = client_id
            cred_data["client_secret"] = client_secret
        else:
            return f"❌ client_id et client_secret requis pour {name} (OAuth2)"

    save_credential(name, cred_data)
    return f"✅ {config['name']} connecté avec succès!"


@tool("integrations_disconnect", "Déconnecte une intégration")
async def integrations_disconnect(name: str) -> str:
    """Déconnecte une intégration."""
    delete_credential(name)
    config = INTEGRATION_DEFS.get(name, {})
    return f"✅ {config.get('name', name)} déconnecté."


@tool("integrations_execute", "Exécute une action sur une intégration connectée")
async def integrations_execute(integration: str, action: str, params: str = "") -> str:
    """Exécute une action sur une intégration.

    Args:
        integration: Nom de l'intégration (slack, github, notion, etc.)
        action: Nom de l'action (send_message, list_repos, etc.)
        params: Paramètres au format key=value,key2=value2
    """
    # Parser les paramètres
    parsed_params = {}
    if params:
        for part in params.split(","):
            if "=" in part:
                k, v = part.split("=", 1)
                parsed_params[k.strip()] = v.strip()

    result = await execute_action(integration, action, parsed_params)
    return result


@tool("integrations_setup_slack", "Configure rapidement Slack avec un bot token")
async def integrations_setup_slack(bot_token: str) -> str:
    """Configure Slack rapidement avec un bot token (xoxb-...)."""
    if not bot_token.startswith("xoxb-"):
        return "❌ Token invalide. Un bot token Slack commence par 'xoxb-'"
    save_credential("slack", {"token": bot_token})
    return "✅ Slack connecté! Tu peux maintenant envoyer des messages avec integrations_execute(integration='slack', action='send_message', params='channel=C01234567,message=Hello')"


@tool("integrations_setup_github", "Configure rapidement GitHub avec un token")
async def integrations_setup_github(token: str) -> str:
    """Configure GitHub avec un token (ghp_...)."""
    if not token.startswith("ghp_") and not token.startswith("github_pat-"):
        return "❌ Token invalide. Un token GitHub commence par 'ghp_' ou 'github_pat-'"
    save_credential("github", {"token": token})
    return "✅ GitHub connecté! Tu peux maintenant lister tes repos avec integrations_execute(integration='github', action='list_repos')"


@tool("integrations_setup_telegram", "Configure rapidement Telegram avec un bot token")
async def integrations_setup_telegram(bot_token: str) -> str:
    """Configure Telegram avec un bot token (obtenu via @BotFather)."""
    save_credential("telegram", {"token": bot_token})
    return "✅ Telegram connecté! Tu peux maintenant envoyer des messages."
