"""Outils LLM pour les workflows Alex — permet à Alex de gérer les automatisations."""
import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Import du moteur de workflows
try:
    from ..workflow.engine import WorkflowEngine, Workflow, WorkflowNode, WorkflowConnection
    from ..workflow.nodes import NodeRegistry
    from ..workflow.credentials import CredentialManager
    _workflow_available = True
except ImportError:
    _workflow_available = False
    logger.warning("Workflow module not available")


def _get_engine():
    """Récupère l'instance du moteur de workflows."""
    if not _workflow_available:
        return None
    from ..workflow.routes import _workflow_engine
    return _workflow_engine


def _get_registry():
    """Récupère le registre des nodes."""
    if not _workflow_available:
        return None
    from ..workflow.routes import _node_registry
    return _node_registry


# ─── Outils pour Alex ──────────────────────────────────────────────────────

from . import tool

@tool("workflows_list", "Liste tous les workflows d'automatisation disponibles")
async def workflows_list() -> str:
    """Liste tous les workflows."""
    engine = _get_engine()
    if not engine:
        return json.dumps({"error": "Workflow engine not available"})
    
    workflows = engine.list_workflows()
    return json.dumps({"workflows": workflows, "count": len(workflows)}, ensure_ascii=False)


@tool("workflows_create", "Crée un nouveau workflow d'automatisation avec des étapes", dangerous=True)
async def workflows_create(name: str, steps: list, description: str = "") -> str:
    """
    Crée un workflow à partir des paramètres.
    
    Args:
        name: Nom du workflow
        steps: Liste des étapes [{type, name, params}]
        description: Description du workflow
    """
    engine = _get_engine()
    if not engine:
        return json.dumps({"error": "Workflow engine not available"})
    
    # Convertir les étapes en nodes
    nodes = []
    connections = []
    
    for i, step in enumerate(steps):
        node_id = f"node_{i+1}"
        node = WorkflowNode(
            id=node_id,
            type=step.get("type", "condition"),
            name=step.get("name", f"Étape {i+1}"),
            params=step.get("params", {}),
            position=[100 + i * 200, 200]
        )
        nodes.append(node)
        
        # Connecter au node précédent
        if i > 0:
            connections.append(WorkflowConnection(
                source_node_id=f"node_{i}",
                target_node_id=node_id
            ))
    
    workflow = engine.create_workflow(name, description, nodes, connections)
    
    return json.dumps({
        "success": True,
        "workflow_id": workflow.id,
        "name": workflow.name,
        "nodes_count": len(nodes),
        "message": f"Workflow '{name}' créé avec {len(nodes)} étapes"
    }, ensure_ascii=False)


@tool("workflows_execute", "Exécute un workflow existant", dangerous=True)
async def workflows_execute(workflow_id: str) -> str:
    """
    Exécute un workflow.
    
    Args:
        workflow_id: ID du workflow à exécuter
    """
    engine = _get_engine()
    if not engine:
        return json.dumps({"error": "Workflow engine not available"})
    
    if not workflow_id:
        return json.dumps({"error": "workflow_id requis"})
    
    try:
        execution = await engine.execute_workflow(workflow_id, {"trigger": "manual"})
        return json.dumps({
            "success": True,
            "execution_id": execution.execution_id,
            "status": execution.status,
            "duration_ms": (execution.completed_at - execution.started_at) * 1000,
            "nodes_executed": len(execution.node_results)
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


@tool("workflows_delete", "Supprime un workflow", dangerous=True)
async def workflows_delete(workflow_id: str) -> str:
    """
    Supprime un workflow.
    
    Args:
        workflow_id: ID du workflow à supprimer
    """
    engine = _get_engine()
    if not engine:
        return json.dumps({"error": "Workflow engine not available"})
    
    if not workflow_id:
        return json.dumps({"error": "workflow_id requis"})
    
    success = engine.delete_workflow(workflow_id)
    return json.dumps({
        "success": success,
        "message": "Workflow supprimé" if success else "Workflow non trouvé"
    })


@tool("workflows_get", "Récupère les détails d'un workflow")
async def workflows_get(workflow_id: str) -> str:
    """
    Récupère les détails d'un workflow.
    
    Args:
        workflow_id: ID du workflow
    """
    engine = _get_engine()
    if not engine:
        return json.dumps({"error": "Workflow engine not available"})
    
    if not workflow_id:
        return json.dumps({"error": "workflow_id requis"})
    
    workflow = engine.get_workflow(workflow_id)
    if not workflow:
        return json.dumps({"error": "Workflow non trouvé"})
    
    return json.dumps(workflow.to_dict(), ensure_ascii=False)


@tool("workflows_list_nodes", "Liste les types d'actions disponibles pour créer des workflows")
async def workflows_list_nodes(category: str = "") -> str:
    """
    Liste les nodes disponibles.
    
    Args:
        category: Filtrer par catégorie (trigger, action, condition, transform)
    """
    registry = _get_registry()
    if not registry:
        return json.dumps({"error": "Node registry not available"})
    
    nodes = registry.list_nodes(category if category else None)
    return json.dumps({"nodes": nodes, "count": len(nodes)}, ensure_ascii=False)


@tool("workflows_create_from_description", "Crée un workflow à partir d'une description en langage naturel", dangerous=True)
async def workflows_create_from_description(description: str) -> str:
    """
    Crée un workflow à partir d'une description en langage naturel.
    Alex interprète et crée le workflow automatiquement.
    
    Args:
        description: Description en langage naturel du workflow souhaité
    """
    engine = _get_engine()
    if not engine:
        return json.dumps({"error": "Workflow engine not available"})
    
    if not description:
        return json.dumps({"error": "description requise"})
    
    # Analyser la description et créer le workflow
    description_lower = description.lower()
    
    nodes = []
    connections = []
    
    # Détecter les patterns courants
    if "gmail" in description_lower and ("slack" in description_lower or "notif" in description_lower):
        # Workflow Gmail → Slack
        nodes = [
            WorkflowNode(id="node_1", type="gmail_read", name="Lire Emails", 
                        params={"max_results": 1}, position=[100, 200]),
            WorkflowNode(id="node_2", type="condition", name="Vérifier Expéditeur",
                        params={"field": "from", "operator": "contains", "value": "important"}, position=[300, 200]),
            WorkflowNode(id="node_3", type="slack_send_message", name="Notifier Slack",
                        params={"channel": "#general", "text": "Email important reçu!"}, position=[500, 200])
        ]
        connections = [
            WorkflowConnection(source_node_id="node_1", target_node_id="node_2"),
            WorkflowConnection(source_node_id="node_2", target_node_id="node_3")
        ]
        name = "Gmail → Slack Notification"
    
    elif "github" in description_lower and ("discord" in description_lower or "notif" in description_lower):
        # Workflow GitHub → Discord
        nodes = [
            WorkflowNode(id="node_1", type="webhook_trigger", name="Webhook GitHub",
                        params={"path": "/github/pr", "method": "POST"}, position=[100, 200]),
            WorkflowNode(id="node_2", type="discord_send_message", name="Notifier Discord",
                        params={"channel_id": "", "text": "Nouvelle PR créée!"}, position=[300, 200])
        ]
        connections = [
            WorkflowConnection(source_node_id="node_1", target_node_id="node_2")
        ]
        name = "GitHub → Discord Notification"
    
    elif "rapport" in description_lower or "quotidien" in description_lower or "daily" in description_lower:
        # Workflow Rapport quotidien
        nodes = [
            WorkflowNode(id="node_1", type="schedule_trigger", name="Chaque matin",
                        params={"cron": "0 9 * * *"}, position=[100, 200]),
            WorkflowNode(id="node_2", type="http_request", name="Récupérer Données",
                        params={"url": "https://api.example.com/daily", "method": "GET"}, position=[300, 200]),
            WorkflowNode(id="node_3", type="gmail_send", name="Envoyer Rapport",
                        params={"to": "moi@example.com", "subject": "Rapport du jour", "body": "{{data}}"}, position=[500, 200])
        ]
        connections = [
            WorkflowConnection(source_node_id="node_1", target_node_id="node_2"),
            WorkflowConnection(source_node_id="node_2", target_node_id="node_3")
        ]
        name = "Rapport Quotidien"
    
    else:
        # Workflow par défaut avec une action HTTP
        nodes = [
            WorkflowNode(id="node_1", type="http_request", name="Requête HTTP",
                        params={"url": "https://api.example.com", "method": "GET"}, position=[100, 200])
        ]
        name = f"Workflow: {description[:50]}"
    
    workflow = engine.create_workflow(name, description, nodes, connections)
    
    return json.dumps({
        "success": True,
        "workflow_id": workflow.id,
        "name": workflow.name,
        "nodes_count": len(nodes),
        "message": f"Workflow '{workflow.name}' créé automatiquement à partir de ta description"
    }, ensure_ascii=False)
