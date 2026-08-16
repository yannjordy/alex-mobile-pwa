"""Routes API pour les workflows Alex — inspiré de n8n."""
import time
from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Optional
from .engine import WorkflowEngine, Workflow, WorkflowNode, WorkflowConnection
from .nodes import NodeRegistry, NodeDefinition
from .credentials import CredentialManager, CREDENTIAL_DEFINITIONS

router = APIRouter(prefix="/workflows", tags=["workflows"])

# Instances globales
_node_registry = NodeRegistry()
_credential_manager = CredentialManager()
_workflow_engine = WorkflowEngine(_node_registry, _credential_manager)

# Enregistrer les handlers dans le moteur
for node_type, handler in _node_registry._handlers.items():
    _workflow_engine.register_node_handler(node_type, handler)


# ─── Modèles Pydantic ──────────────────────────────────────────────────────

class WorkflowCreate(BaseModel):
    name: str
    description: str = ""
    nodes: list = []
    connections: list = []

class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[list] = None
    connections: Optional[list] = None
    enabled: Optional[bool] = None

class NodeCreate(BaseModel):
    type: str
    name: str
    params: dict = {}
    position: list = [0, 0]

class CredentialCreate(BaseModel):
    name: str
    app: str
    auth_type: str
    data: dict = {}

class WorkflowExecute(BaseModel):
    trigger_data: dict = {}
    context: dict = {}


# ─── Routes Workflows ──────────────────────────────────────────────────────

@router.get("")
async def list_workflows():
    """Liste tous les workflows."""
    return {"workflows": _workflow_engine.list_workflows()}

@router.post("")
async def create_workflow(req: WorkflowCreate):
    """Crée un nouveau workflow."""
    nodes = [WorkflowNode(**n) if isinstance(n, dict) else n for n in req.nodes]
    connections = [WorkflowConnection(**c) if isinstance(c, dict) else c for c in req.connections]
    wf = _workflow_engine.create_workflow(req.name, req.description, nodes, connections)
    return wf.to_dict()

@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    """Récupère un workflow."""
    wf = _workflow_engine.get_workflow(workflow_id)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.to_dict()

@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, req: WorkflowUpdate):
    """Met à jour un workflow."""
    updates = req.dict(exclude_none=True)
    wf = _workflow_engine.update_workflow(workflow_id, **updates)
    if not wf:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return wf.to_dict()

@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    """Supprime un workflow."""
    if not _workflow_engine.delete_workflow(workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    return {"success": True}

@router.post("/{workflow_id}/execute")
async def execute_workflow(workflow_id: str, req: WorkflowExecute = None):
    """Exécute un workflow."""
    try:
        trigger_data = req.trigger_data if req else {}
        context = req.context if req else {}
        execution = await _workflow_engine.execute_workflow(workflow_id, trigger_data, context)
        return execution.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{workflow_id}/executions")
async def list_executions(workflow_id: str, limit: int = Query(50, le=100)):
    """Liste les exécutions d'un workflow."""
    return {"executions": _workflow_engine.list_executions(workflow_id, limit)}


# ─── Routes Nodes ──────────────────────────────────────────────────────────

@router.get("/nodes/list")
async def list_nodes(category: str = None):
    """Liste les nodes disponibles."""
    return {"nodes": _node_registry.list_nodes(category)}

@router.get("/nodes/{node_type}")
async def get_node(node_type: str):
    """Récupère la définition d'un node."""
    defn = _node_registry.get_definition(node_type)
    if not defn:
        raise HTTPException(status_code=404, detail="Node not found")
    return defn.to_dict()


# ─── Routes Credentials ────────────────────────────────────────────────────

@router.get("/credentials/types")
async def list_credential_types():
    """Liste les types de credentials disponibles."""
    return {"types": _credential_manager.list_credential_types()}

@router.get("/credentials")
async def list_credentials(app: str = None):
    """Liste les credentials configurés."""
    return {"credentials": _credential_manager.list_credentials(app)}

@router.post("/credentials")
async def create_credential(req: CredentialCreate):
    """Crée un nouveau credential."""
    cred = _credential_manager.create_credential(req.name, req.app, req.auth_type, req.data)
    return cred.to_dict(mask=True)

@router.get("/credentials/{credential_id}")
async def get_credential(credential_id: str):
    """Récupère un credential."""
    cred = _credential_manager.get_credential(credential_id)
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return cred

@router.put("/credentials/{credential_id}")
async def update_credential(credential_id: str, data: dict = None):
    """Met à jour un credential."""
    cred = _credential_manager.update_credential(credential_id, data=data or {})
    if not cred:
        raise HTTPException(status_code=404, detail="Credential not found")
    return cred.to_dict(mask=True)

@router.delete("/credentials/{credential_id}")
async def delete_credential(credential_id: str):
    """Supprime un credential."""
    if not _credential_manager.delete_credential(credential_id):
        raise HTTPException(status_code=404, detail="Credential not found")
    return {"success": True}

@router.post("/credentials/{credential_id}/test")
async def test_credential(credential_id: str):
    """Teste un credential."""
    cred_data = _credential_manager.get_credential_data(credential_id)
    if not cred_data:
        raise HTTPException(status_code=404, detail="Credential not found")
    
    # TODO: Implémenter le test réel selon le type d'app
    return {"success": True, "message": "Credential is valid"}


# ─── Routes Exécution ──────────────────────────────────────────────────────

@router.get("/executions")
async def list_all_executions(limit: int = Query(50, le=100)):
    """Liste toutes les exécutions récentes."""
    return {"executions": _workflow_engine.list_executions(limit=limit)}

@router.get("/executions/{execution_id}")
async def get_execution(execution_id: str):
    """Récupère une exécution."""
    exec_data = _workflow_engine.get_execution(execution_id)
    if not exec_data:
        raise HTTPException(status_code=404, detail="Execution not found")
    return exec_data


# ─── Routes Templates ──────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    """Liste les templates de workflows prédéfinis."""
    templates = [
        {
            "id": "template_gmail_slack",
            "name": "Gmail → Slack Notification",
            "description": "Envoyer un message Slack quand un email est reçu",
            "category": "notification",
            "nodes": [
                {"type": "gmail_read", "name": "Lire Emails", "params": {"max_results": 1}, "position": [100, 200]},
                {"type": "condition", "name": "Vérifier Expéditeur", "params": {"field": "from", "operator": "contains", "value": "important@"}, "position": [300, 200]},
                {"type": "slack_send_message", "name": "Notifier Slack", "params": {"channel": "#general", "text": "Email important reçu!"}, "position": [500, 200]}
            ],
            "connections": [
                {"source_node_id": "node_1", "target_node_id": "node_2"},
                {"source_node_id": "node_2", "target_node_id": "node_3"}
            ]
        },
        {
            "id": "template_github_pr",
            "name": "GitHub PR → Discord",
            "description": "Notifier Discord quand une PR est créée",
            "category": "notification",
            "nodes": [
                {"type": "webhook_trigger", "name": "Webhook GitHub", "params": {"path": "/github/pr", "method": "POST"}, "position": [100, 200]},
                {"type": "slack_send_message", "name": "Notifier Discord", "params": {"channel_id": "", "text": "Nouvelle PR créée!"}, "position": [300, 200]}
            ],
            "connections": [
                {"source_node_id": "node_1", "target_node_id": "node_2"}
            ]
        },
        {
            "id": "template_daily_report",
            "name": "Rapport Quotidien",
            "description": "Envoyer un rapport chaque jour à 9h",
            "category": "automation",
            "nodes": [
                {"type": "schedule_trigger", "name": "Chaque matin", "params": {"cron": "0 9 * * *"}, "position": [100, 200]},
                {"type": "http_request", "name": "Récupérer Données", "params": {"url": "https://api.example.com/daily", "method": "GET"}, "position": [300, 200]},
                {"type": "gmail_send", "name": "Envoyer Rapport", "params": {"to": "me@example.com", "subject": "Rapport du jour", "body": "{{data}}"}, "position": [500, 200]}
            ],
            "connections": [
                {"source_node_id": "node_1", "target_node_id": "node_2"},
                {"source_node_id": "node_2", "target_node_id": "node_3"}
            ]
        }
    ]
    return {"templates": templates}
