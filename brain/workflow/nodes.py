"""Système de nodes pour les workflows Alex — inspiré des nodes n8n."""
import json
import aiohttp
import logging
from typing import Any, Optional, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

@dataclass
class NodePort:
    """Port d'entrée ou de sortie d'un node."""
    name: str
    type: str = "any"  # any, string, number, boolean, object, array
    required: bool = False
    default: Any = None
    description: str = ""

@dataclass
class NodeDefinition:
    """Définition d'un type de node."""
    type: str
    name: str
    category: str  # trigger, action, condition, transform
    description: str = ""
    icon: str = "⚙️"
    color: str = "#666666"
    inputs: list = field(default_factory=list)  # List[NodePort]
    outputs: list = field(default_factory=list)  # List[NodePort]
    params: list = field(default_factory=list)   # Paramètres configurables
    
    def to_dict(self):
        return {
            'type': self.type,
            'name': self.name,
            'category': self.category,
            'description': self.description,
            'icon': self.icon,
            'color': self.color,
            'inputs': [asdict(i) for i in self.inputs],
            'outputs': [asdict(o) for o in self.outputs],
            'params': [asdict(p) for p in self.params]
        }


class BaseNode(ABC):
    """Classe de base pour tous les nodes."""
    
    @abstractmethod
    def get_definition(self) -> NodeDefinition:
        """Retourne la définition du node."""
        pass
    
    @abstractmethod
    async def execute(self, inputs: dict, context: dict) -> Any:
        """Exécute le node."""
        pass


class TriggerNode(BaseNode):
    """Node de déclenchement (manuel, webhook, schedule)."""
    
    def get_definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="trigger_manual",
            name="Déclenchement Manuel",
            category="trigger",
            description="Déclenche le workflow manuellement",
            icon="▶️",
            color="#4CAF50"
        )
    
    async def execute(self, inputs: dict, context: dict) -> Any:
        return {"triggered": True, "timestamp": context.get('timestamp')}


class ActionNode(BaseNode):
    """Node d'action (API call, email, etc.)."""
    
    def __init__(self, definition: NodeDefinition, handler: Callable):
        self._definition = definition
        self._handler = handler
    
    def get_definition(self) -> NodeDefinition:
        return self._definition
    
    async def execute(self, inputs: dict, context: dict) -> Any:
        return await self._handler(inputs, context)


class ConditionNode(BaseNode):
    """Node de condition (if/else)."""
    
    def get_definition(self) -> NodeDefinition:
        return NodeDefinition(
            type="condition",
            name="Condition",
            category="condition",
            description="Vérifie une condition et route vers différentes branches",
            icon="🔀",
            color="#FF9800",
            params=[
                NodePort(name="field", type="string", required=True, description="Champ à vérifier"),
                NodePort(name="operator", type="string", required=True, description="Opérateur (equals, contains, gt, lt, etc.)"),
                NodePort(name="value", type="any", required=True, description="Valeur de comparaison")
            ]
        )
    
    async def execute(self, inputs: dict, context: dict) -> Any:
        field_name = inputs.get('field', '')
        operator = inputs.get('operator', 'equals')
        expected = inputs.get('value')
        actual = inputs.get(field_name) or context.get(field_name)
        
        result = False
        if operator == 'equals':
            result = actual == expected
        elif operator == 'not_equals':
            result = actual != expected
        elif operator == 'contains':
            result = str(expected) in str(actual) if actual else False
        elif operator == 'gt':
            result = float(actual) > float(expected) if actual else False
        elif operator == 'lt':
            result = float(actual) < float(expected) if actual else False
        elif operator == 'starts_with':
            result = str(actual).startswith(str(expected)) if actual else False
        elif operator == 'ends_with':
            result = str(actual).endswith(str(expected)) if actual else False
        
        return {"result": result, "branch": "true" if result else "false"}


class NodeRegistry:
    """Registre des nodes disponibles."""
    
    def __init__(self):
        self._nodes: dict[str, NodeDefinition] = {}
        self._handlers: dict[str, Callable] = {}
        self._register_builtins()
    
    def _register_builtins(self):
        """Enregistre les nodes de base."""
        # Trigger
        trigger = TriggerNode()
        defn = trigger.get_definition()
        self._nodes[defn.type] = defn
        self._handlers[defn.type] = trigger.execute
        
        # Condition
        condition = ConditionNode()
        defn = condition.get_definition()
        self._nodes[defn.type] = defn
        self._handlers[defn.type] = condition.execute
        
        # Enregistrer les nodes d'intégration
        self._register_integration_nodes()
    
    def _register_integration_nodes(self):
        """Enregistre les nodes pour les intégrations."""
        
        # Gmail
        self.register(NodeDefinition(
            type="gmail_send",
            name="Gmail - Envoyer Email",
            category="action",
            description="Envoyer un email via Gmail",
            icon="📧",
            color="#EA4335",
            params=[
                NodePort(name="to", type="string", required=True, description="Destinataire"),
                NodePort(name="subject", type="string", required=True, description="Objet"),
                NodePort(name="body", type="string", required=True, description="Contenu"),
                NodePort(name="cc", type="string", description="CC"),
                NodePort(name="attachments", type="array", description="Pièces jointes (URLs)")
            ]
        ), self._gmail_send_handler)
        
        self.register(NodeDefinition(
            type="gmail_read",
            name="Gmail - Lire Emails",
            category="action",
            description="Lire les emails Gmail",
            icon="📨",
            color="#EA4335",
            params=[
                NodePort(name="query", type="string", description="Recherche"),
                NodePort(name="max_results", type="number", description="Nombre max")
            ]
        ), self._gmail_read_handler)
        
        # Slack
        self.register(NodeDefinition(
            type="slack_send_message",
            name="Slack - Envoyer Message",
            category="action",
            description="Envoyer un message Slack",
            icon="💬",
            color="#4A154B",
            params=[
                NodePort(name="channel", type="string", required=True, description="Canal"),
                NodePort(name="text", type="string", required=True, description="Message"),
                NodePort(name="thread_ts", type="string", description="Thread parent")
            ]
        ), self._slack_send_handler)
        
        self.register(NodeDefinition(
            type="slack_list_channels",
            name="Slack - Lister Canaux",
            category="action",
            description="Lister les canaux Slack",
            icon="📋",
            color="#4A154B"
        ), self._slack_list_channels_handler)
        
        # GitHub
        self.register(NodeDefinition(
            type="github_create_issue",
            name="GitHub - Créer Issue",
            category="action",
            description="Créer une issue GitHub",
            icon="🐛",
            color="#24292e",
            params=[
                NodePort(name="repo", type="string", required=True, description="Dépôt (owner/repo)"),
                NodePort(name="title", type="string", required=True, description="Titre"),
                NodePort(name="body", type="string", description="Description"),
                NodePort(name="labels", type="array", description="Labels")
            ]
        ), self._github_create_issue_handler)
        
        self.register(NodeDefinition(
            type="github_create_pr",
            name="GitHub - Créer PR",
            category="action",
            description="Créer une Pull Request",
            icon="🔀",
            color="#24292e",
            params=[
                NodePort(name="repo", type="string", required=True, description="Dépôt"),
                NodePort(name="title", type="string", required=True, description="Titre"),
                NodePort(name="head", type="string", required=True, description="Branche source"),
                NodePort(name="base", type="string", required=True, description="Branche cible"),
                NodePort(name="body", type="string", description="Description")
            ]
        ), self._github_create_pr_handler)
        
        # Telegram
        self.register(NodeDefinition(
            type="telegram_send_message",
            name="Telegram - Envoyer Message",
            category="action",
            description="Envoyer un message Telegram",
            icon="✈️",
            color="#0088cc",
            params=[
                NodePort(name="chat_id", type="string", required=True, description="Chat ID"),
                NodePort(name="text", type="string", required=True, description="Message"),
                NodePort(name="parse_mode", type="string", description="HTML/Markdown")
            ]
        ), self._telegram_send_handler)
        
        # Discord
        self.register(NodeDefinition(
            type="discord_send_message",
            name="Discord - Envoyer Message",
            category="action",
            description="Envoyer un message Discord",
            icon="🎮",
            color="#5865F2",
            params=[
                NodePort(name="channel_id", type="string", required=True, description="Channel ID"),
                NodePort(name="content", type="string", required=True, description="Message")
            ]
        ), self._discord_send_handler)
        
        # HTTP Request
        self.register(NodeDefinition(
            type="http_request",
            name="Requête HTTP",
            category="action",
            description="Envoyer une requête HTTP",
            icon="🌐",
            color="#2196F3",
            params=[
                NodePort(name="url", type="string", required=True, description="URL"),
                NodePort(name="method", type="string", description="Méthode (GET, POST, etc.)"),
                NodePort(name="headers", type="object", description="Headers"),
                NodePort(name="body", type="any", description="Corps de la requête")
            ]
        ), self._http_request_handler)
        
        # Webhook (trigger)
        self.register(NodeDefinition(
            type="webhook_trigger",
            name="Webhook",
            category="trigger",
            description="Déclenche quand un webhook est reçu",
            icon="🔔",
            color="#9C27B0",
            params=[
                NodePort(name="path", type="string", required=True, description="Chemin du webhook"),
                NodePort(name="method", type="string", description="Méthode (GET, POST)")
            ]
        ), self._webhook_trigger_handler)
        
        # Schedule (trigger)
        self.register(NodeDefinition(
            type="schedule_trigger",
            name="Planification",
            category="trigger",
            description="Déclenche à intervalle régulier",
            icon="⏰",
            color="#607D8B",
            params=[
                NodePort(name="cron", type="string", required=True, description="Expression cron"),
                NodePort(name="interval_minutes", type="number", description="Intervalle en minutes")
            ]
        ), self._schedule_trigger_handler)
        
        # Delay
        self.register(NodeDefinition(
            type="delay",
            name="Attendre",
            category="transform",
            description="Attendre un certain temps",
            icon="⏳",
            color="#795548",
            params=[
                NodePort(name="seconds", type="number", required=True, description="Secondes à attendre")
            ]
        ), self._delay_handler)
        
        # Code (transform)
        self.register(NodeDefinition(
            type="code",
            name="Code Python",
            category="transform",
            description="Exécuter du code Python personnalisé",
            icon="🐍",
            color="#3776AB",
            params=[
                NodePort(name="code", type="string", required=True, description="Code à exécuter"),
                NodePort(name="input_data", type="any", description="Données d'entrée")
            ]
        ), self._code_handler)
    
    def register(self, definition: NodeDefinition, handler: Callable):
        """Enregistre un node."""
        self._nodes[definition.type] = definition
        self._handlers[definition.type] = handler
    
    def get_definition(self, node_type: str) -> Optional[NodeDefinition]:
        """Récupère la définition d'un node."""
        return self._nodes.get(node_type)
    
    def get_handler(self, node_type: str) -> Optional[Callable]:
        """Récupère le handler d'un node."""
        return self._handlers.get(node_type)
    
    def list_nodes(self, category: str = None) -> list:
        """Liste les nodes disponibles."""
        nodes = list(self._nodes.values())
        if category:
            nodes = [n for n in nodes if n.category == category]
        return [n.to_dict() for n in nodes]
    
    def execute_node(self, node_type: str, inputs: dict, context: dict):
        """Exécute un node."""
        handler = self._handlers.get(node_type)
        if not handler:
            raise ValueError(f"Unknown node type: {node_type}")
        return handler(inputs, context)
    
    # ─── Handlers pour les intégrations ─────────────────────────────────────
    
    async def _gmail_send_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour Gmail - Envoyer email."""
        to = inputs.get('to')
        subject = inputs.get('subject')
        body = inputs.get('body')
        # TODO: Implémenter avec l'API Gmail
        logger.info(f"Gmail: Sending email to {to} with subject '{subject}'")
        return {"success": True, "message_id": f"msg_{context.get('timestamp', 'now')}"}
    
    async def _gmail_read_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour Gmail - Lire emails."""
        # TODO: Implémenter avec l'API Gmail
        return {"emails": [], "count": 0}
    
    async def _slack_send_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour Slack - Envoyer message."""
        channel = inputs.get('channel')
        text = inputs.get('text')
        logger.info(f"Slack: Sending to #{channel}: {text[:50]}...")
        # TODO: Implémenter avec l'API Slack
        return {"success": True, "ts": f"ts_{context.get('timestamp', 'now')}"}
    
    async def _slack_list_channels_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour Slack - Lister canaux."""
        # TODO: Implémenter avec l'API Slack
        return {"channels": []}
    
    async def _github_create_issue_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour GitHub - Créer issue."""
        repo = inputs.get('repo')
        title = inputs.get('title')
        logger.info(f"GitHub: Creating issue in {repo}: {title}")
        # TODO: Implémenter avec l'API GitHub
        return {"success": True, "issue_number": 1, "url": f"https://github.com/{repo}/issues/1"}
    
    async def _github_create_pr_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour GitHub - Créer PR."""
        repo = inputs.get('repo')
        title = inputs.get('title')
        logger.info(f"GitHub: Creating PR in {repo}: {title}")
        # TODO: Implémenter avec l'API GitHub
        return {"success": True, "pr_number": 1, "url": f"https://github.com/{repo}/pull/1"}
    
    async def _telegram_send_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour Telegram - Envoyer message."""
        chat_id = inputs.get('chat_id')
        text = inputs.get('text')
        logger.info(f"Telegram: Sending to {chat_id}: {text[:50]}...")
        # TODO: Implémenter avec l'API Telegram
        return {"success": True, "message_id": context.get('timestamp', 'now')}
    
    async def _discord_send_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour Discord - Envoyer message."""
        channel_id = inputs.get('channel_id')
        content = inputs.get('content')
        logger.info(f"Discord: Sending to {channel_id}: {content[:50]}...")
        # TODO: Implémenter avec l'API Discord
        return {"success": True, "message_id": context.get('timestamp', 'now')}
    
    async def _http_request_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour requête HTTP."""
        url = inputs.get('url')
        method = inputs.get('method', 'GET').upper()
        headers = inputs.get('headers', {})
        body = inputs.get('body')
        
        logger.info(f"HTTP: {method} {url}")
        
        try:
            async with aiohttp.ClientSession() as session:
                kwargs = {'headers': headers}
                if body:
                    kwargs['json'] = body if isinstance(body, dict) else body
                
                async with session.request(method, url, **kwargs) as response:
                    content = await response.text()
                    try:
                        json_content = json.loads(content)
                    except:
                        json_content = content
                    
                    return {
                        "status": response.status,
                        "headers": dict(response.headers),
                        "body": json_content
                    }
        except Exception as e:
            return {"error": str(e)}
    
    async def _webhook_trigger_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour webhook trigger."""
        return {"triggered": True, "data": context.get('webhook_data', {})}
    
    async def _schedule_trigger_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour schedule trigger."""
        return {"triggered": True, "cron": inputs.get('cron')}
    
    async def _delay_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour delay."""
        import asyncio
        seconds = inputs.get('seconds', 1)
        await asyncio.sleep(seconds)
        return {"delayed": seconds}
    
    async def _code_handler(self, inputs: dict, context: dict) -> dict:
        """Handler pour code Python."""
        code = inputs.get('code', '')
        input_data = inputs.get('input_data', {})
        
        logger.info(f"Executing custom Python code ({len(code)} chars)")
        
        # Exécuter le code de manière sécurisée
        try:
            local_vars = {'input': input_data, 'context': context}
            exec(code, {"__builtins__": {}}, local_vars)
            return {"output": local_vars.get('output', None)}
        except Exception as e:
            return {"error": str(e)}
