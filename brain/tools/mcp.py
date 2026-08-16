import subprocess
import json
import os

from . import tool

_MCP_SERVERS: dict[str, dict] = {}


@tool("mcp_install",
      "🔌 Installe un serveur MCP (Model Context Protocol) pour donner accès "
      "à des APIs externes (GitHub, Gmail, Notion, etc.). "
      "Usage : mcp_install nom commande [args...]",
      dangerous=True)
def mcp_install(name: str = "", command: str = "", args: str = "") -> str:
    if not name or not command:
        return "❌ Usage : mcp_install nom commande [args...]"
    parts = [command] + (args.split() if args else [])
    _MCP_SERVERS[name] = {"command": parts[0], "args": parts[1:]}
    return f"🔌 Serveur MCP « {name} » installé. Utilise mcp_call {name} pour l'appeler."


@tool("mcp_list", "🔌 Liste les serveurs MCP installés.")
def mcp_list() -> str:
    if not _MCP_SERVERS:
        return "🔌 Aucun serveur MCP installé. Utilise mcp_install pour en ajouter."
    lines = ["🔌 Serveurs MCP installés :"]
    for name, cfg in _MCP_SERVERS.items():
        lines.append(f"  • {name} → {cfg['command']} {' '.join(cfg['args'])}")
    return "\n".join(lines)


@tool("mcp_call",
      "🔌 Appelle un outil sur un serveur MCP installé avec des paramètres JSON.")
def mcp_call(server: str = "", tool_name: str = "", params: str = "{}") -> str:
    if server not in _MCP_SERVERS:
        return f"❌ Serveur MCP « {server} » inconnu. Utilise mcp_list pour voir les serveurs disponibles."
    cfg = _MCP_SERVERS[server]
    try:
        p = subprocess.run(
            [cfg["command"]] + cfg["args"],
            input=json.dumps({"tool": tool_name, "params": params}),
            capture_output=True, text=True, timeout=30
        )
        if p.returncode == 0:
            return p.stdout.strip() or "✅ Commande MCP exécutée."
        return f"❌ Erreur MCP : {p.stderr.strip()[:300]}"
    except subprocess.TimeoutExpired:
        return "❌ Timeout du serveur MCP."
    except Exception as e:
        return f"❌ Erreur MCP : {e}"


@tool("github_mcp",
      "🔌 Configure et appelle l'API GitHub via MCP — issues, PRs, repos, codesearch. "
      "Usage : github_mcp action [params...]",
      dangerous=True)
def github_mcp(action: str = "", token: str = "", owner: str = "", repo: str = "", params: str = "{}") -> str:
    if not action:
        return ("🔌 Actions GitHub disponibles :\n"
                "  • search_code query  → cherche du code\n"
                "  • list_issues owner repo  → liste les issues\n"
                "  • create_issue owner repo title body  → crée une issue\n"
                "  • list_prs owner repo  → liste les PRs\n"
                "  • get_file owner repo path  → lit un fichier")
    gh_token = token or os.environ.get("GITHUB_TOKEN", "")
    if not gh_token:
        return "❌ Token GitHub requis. Définis GITHUB_TOKEN dans .env ou passe-le en paramètre."

    try:
        if action == "search_code":
            query = params or owner
            r = subprocess.run(
                ["curl", "-s", "-H", f"Authorization: token {gh_token}",
                 "-H", "Accept: application/vnd.github.v3+json",
                 f"https://api.github.com/search/code?q={query}&per_page=5"],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(r.stdout)
            items = data.get("items", [])
            if not items:
                return f"Aucun résultat pour « {query} »."
            lines = [f"🔍 Résultats GitHub pour « {query} » :"]
            for item in items[:5]:
                lines.append(f"  • {item['path']} → {item['html_url']}")
            return "\n".join(lines)

        elif action == "list_issues":
            o, r = owner or "octocat", repo or "Hello-World"
            r = subprocess.run(
                ["curl", "-s", "-H", f"Authorization: token {gh_token}",
                 f"https://api.github.com/repos/{o}/{r}/issues?state=open&per_page=5"],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(r.stdout)
            if isinstance(data, dict) and "message" in data:
                return f"❌ {data['message']}"
            lines = [f"📋 Issues ouvertes dans {o}/{r} :"]
            for issue in data[:5]:
                lines.append(f"  • #{issue['number']} {issue['title']}")
            return "\n".join(lines)

        elif action == "create_issue":
            o, r, title, body = owner or "", repo or "", params or "", ""
            if not o or not r or not title:
                return "Usage : github_mcp create_issue owner repo title body"
            r = subprocess.run(
                ["curl", "-s", "-X", "POST", "-H", f"Authorization: token {gh_token}",
                 "-H", "Content-Type: application/json",
                 "-d", json.dumps({"title": title, "body": body}),
                 f"https://api.github.com/repos/{o}/{r}/issues"],
                capture_output=True, text=True, timeout=15
            )
            data = json.loads(r.stdout)
            if "html_url" in data:
                return f"✅ Issue créée : {data['html_url']}"
            return f"❌ {data.get('message', 'Erreur inconnue')}"

        else:
            return f"❌ Action « {action} » inconnue. Actions dispo : search_code, list_issues, create_issue, list_prs, get_file"

    except Exception as e:
        return f"❌ Erreur GitHub : {e}"
