"""Moteur d'exécution de workflows pour Alex — inspiré de n8n."""
import json
import uuid
import time
import asyncio
import logging
from typing import Any, Optional, Callable, Awaitable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)

class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TriggerType(str, Enum):
    MANUAL = "manual"
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    EVENT = "event"

@dataclass
class NodeInput:
    """Entrée d'un node (connexion depuis un autre node)."""
    source_node_id: str
    source_output: str = "output"  # Nom du port de sortie
    target_param: str = "input"    # Nom du paramètre d'entrée cible

@dataclass
class WorkflowNode:
    """Un node (étape) dans un workflow."""
    id: str
    type: str                    # ex: "gmail_send", "condition", "webhook"
    name: str                    # Nom affiché
    params: dict = field(default_factory=dict)  # Paramètres de configuration
    position: tuple = (0, 0)     # Position x,y dans l'éditeur
    inputs: list = field(default_factory=list)   # Connexions entrantes
    enabled: bool = True
    
    def to_dict(self):
        d = asdict(self)
        d['position'] = list(self.position)
        return d
    
    @classmethod
    def from_dict(cls, data: dict):
        data['position'] = tuple(data.get('position', [0, 0]))
        data['inputs'] = [NodeInput(**i) for i in data.get('inputs', [])]
        return cls(**data)

@dataclass
class WorkflowConnection:
    """Connexion entre deux nodes."""
    source_node_id: str
    source_output: str = "output"
    target_node_id: str = ""
    target_param: str = "input"

@dataclass
class NodeExecutionResult:
    """Résultat de l'exécution d'un node."""
    node_id: str
    status: NodeStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    started_at: float = 0
    completed_at: float = 0

@dataclass
class WorkflowExecution:
    """Résultat complet de l'exécution d'un workflow."""
    workflow_id: str
    execution_id: str
    status: NodeStatus
    node_results: dict = field(default_factory=dict)  # node_id -> NodeExecutionResult
    started_at: float = 0
    completed_at: float = 0
    triggered_by: str = "manual"
    
    def to_dict(self):
        d = asdict(self)
        d['node_results'] = {k: asdict(v) if isinstance(v, NodeExecutionResult) else v 
                             for k, v in self.node_results.items()}
        return d

@dataclass
class Workflow:
    """Un workflow complet."""
    id: str
    name: str
    description: str = ""
    nodes: list = field(default_factory=list)  # List[WorkflowNode]
    connections: list = field(default_factory=list)  # List[WorkflowConnection]
    enabled: bool = True
    trigger_type: str = "manual"
    schedule: Optional[str] = None  # Cron expression
    created_at: float = 0
    updated_at: float = 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'nodes': [n.to_dict() if hasattr(n, 'to_dict') else n for n in self.nodes],
            'connections': [asdict(c) if hasattr(c, '__dataclass_fields__') else c for c in self.connections],
            'enabled': self.enabled,
            'trigger_type': self.trigger_type,
            'schedule': self.schedule,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        nodes = [WorkflowNode.from_dict(n) if isinstance(n, dict) else n for n in data.get('nodes', [])]
        connections = []
        for c in data.get('connections', []):
            if isinstance(c, dict):
                connections.append(WorkflowConnection(**c))
            else:
                connections.append(c)
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', 'Untitled'),
            description=data.get('description', ''),
            nodes=nodes,
            connections=connections,
            enabled=data.get('enabled', True),
            trigger_type=data.get('trigger_type', 'manual'),
            schedule=data.get('schedule'),
            created_at=data.get('created_at', time.time()),
            updated_at=data.get('updated_at', time.time())
        )


class WorkflowEngine:
    """Moteur d'exécution de workflows."""
    
    def __init__(self, node_registry=None, credential_manager=None):
        self._workflows: dict[str, Workflow] = {}
        self._executions: dict[str, WorkflowExecution] = {}
        self._node_registry = node_registry
        self._credential_manager = credential_manager
        self._node_handlers: dict[str, Callable] = {}
        self._executions_dir = Path(__file__).parent.parent.parent / "data" / "workflows"
        self._executions_dir.mkdir(parents=True, exist_ok=True)
        self._load_workflows()
    
    def _load_workflows(self):
        """Charge les workflows depuis le disque."""
        workflows_file = self._executions_dir / "workflows.json"
        if workflows_file.exists():
            try:
                with open(workflows_file, 'r') as f:
                    data = json.load(f)
                    for wf_data in data.get('workflows', []):
                        wf = Workflow.from_dict(wf_data)
                        self._workflows[wf.id] = wf
                logger.info(f"Loaded {len(self._workflows)} workflows")
            except Exception as e:
                logger.error(f"Error loading workflows: {e}")
    
    def _save_workflows(self):
        """Sauvegarde les workflows sur le disque."""
        workflows_file = self._executions_dir / "workflows.json"
        try:
            data = {
                'workflows': [wf.to_dict() for wf in self._workflows.values()]
            }
            with open(workflows_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving workflows: {e}")
    
    def register_node_handler(self, node_type: str, handler: Callable):
        """Enregistre un handler pour un type de node."""
        self._node_handlers[node_type] = handler
    
    def create_workflow(self, name: str, description: str = "", nodes: list = None, 
                       connections: list = None) -> Workflow:
        """Crée un nouveau workflow."""
        wf = Workflow(
            id=str(uuid.uuid4()),
            name=name,
            description=description,
            nodes=nodes or [],
            connections=connections or [],
            created_at=time.time(),
            updated_at=time.time()
        )
        self._workflows[wf.id] = wf
        self._save_workflows()
        return wf
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Récupère un workflow par son ID."""
        return self._workflows.get(workflow_id)
    
    def list_workflows(self) -> list:
        """Liste tous les workflows."""
        return [wf.to_dict() for wf in self._workflows.values()]
    
    def update_workflow(self, workflow_id: str, **kwargs) -> Optional[Workflow]:
        """Met à jour un workflow."""
        wf = self._workflows.get(workflow_id)
        if not wf:
            return None
        for key, value in kwargs.items():
            if hasattr(wf, key):
                setattr(wf, key, value)
        wf.updated_at = time.time()
        self._save_workflows()
        return wf
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """Supprime un workflow."""
        if workflow_id in self._workflows:
            del self._workflows[workflow_id]
            self._save_workflows()
            return True
        return False
    
    def _build_execution_order(self, workflow: Workflow) -> list[str]:
        """Construit l'ordre d'exécution des nodes (tri topologique)."""
        node_map = {n.id: n for n in workflow.nodes}
        in_degree = {n.id: 0 for n in workflow.nodes}
        adjacency = {n.id: [] for n in workflow.nodes}
        
        for conn in workflow.connections:
            if conn.target_node_id in in_degree:
                in_degree[conn.target_node_id] += 1
            if conn.source_node_id in adjacency:
                adjacency[conn.source_node_id].append(conn.target_node_id)
        
        # BFS pour tri topologique
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        order = []
        
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            for neighbor in adjacency.get(node_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        return order
    
    def _get_node_inputs(self, node_id: str, workflow: Workflow, 
                         results: dict[str, NodeExecutionResult]) -> dict:
        """Récupère les entrées d'un node depuis les sorties des nodes précédents."""
        inputs = {}
        node = next((n for n in workflow.nodes if n.id == node_id), None)
        if not node:
            return inputs
        
        # Paramètres du node
        inputs.update(node.params)
        
        # Connexions entrantes
        for conn in workflow.connections:
            if conn.target_node_id == node_id:
                source_result = results.get(conn.source_node_id)
                if source_result and source_result.status == NodeStatus.COMPLETED:
                    if isinstance(source_result.output, dict):
                        inputs[conn.target_param] = source_result.output
                    else:
                        inputs[conn.target_param] = source_result.output
        
        return inputs
    
    async def execute_node(self, node: WorkflowNode, inputs: dict, 
                          context: dict = None) -> NodeExecutionResult:
        """Exécute un node individuel."""
        result = NodeExecutionResult(
            node_id=node.id,
            status=NodeStatus.RUNNING,
            started_at=time.time()
        )
        
        try:
            handler = self._node_handlers.get(node.type)
            if not handler:
                raise ValueError(f"No handler for node type: {node.type}")
            
            # Appeler le handler
            if asyncio.iscoroutinefunction(handler):
                output = await handler(inputs, context or {})
            else:
                output = handler(inputs, context or {})
            
            result.output = output
            result.status = NodeStatus.COMPLETED
            
        except Exception as e:
            result.error = str(e)
            result.status = NodeStatus.FAILED
            logger.error(f"Node {node.id} failed: {e}")
        
        result.completed_at = time.time()
        result.duration_ms = (result.completed_at - result.started_at) * 1000
        return result
    
    async def execute_workflow(self, workflow_id: str, trigger_data: dict = None,
                              context: dict = None) -> WorkflowExecution:
        """Exécute un workflow complet."""
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow not found: {workflow_id}")
        
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            execution_id=str(uuid.uuid4()),
            status=NodeStatus.RUNNING,
            started_at=time.time(),
            triggered_by=trigger_data.get('trigger', 'manual') if trigger_data else 'manual'
        )
        
        try:
            # Construire l'ordre d'exécution
            order = self._build_execution_order(workflow)
            
            # Exécuter chaque node
            for node_id in order:
                node = next((n for n in workflow.nodes if n.id == node_id), None)
                if not node or not node.enabled:
                    continue
                
                # Récupérer les entrées
                inputs = self._get_node_inputs(node_id, workflow, execution.node_results)
                
                # Ajouter les données du trigger
                if trigger_data:
                    inputs['trigger'] = trigger_data
                
                # Exécuter le node
                result = await self.execute_node(node, inputs, context)
                execution.node_results[node_id] = result
                
                # Si échec, arrêter (sauf si le node est marqué "continue on error")
                if result.status == NodeStatus.FAILED:
                    execution.status = NodeStatus.FAILED
                    break
            
            if execution.status == NodeStatus.RUNNING:
                execution.status = NodeStatus.COMPLETED
                
        except Exception as e:
            execution.status = NodeStatus.FAILED
            logger.error(f"Workflow {workflow_id} execution failed: {e}")
        
        execution.completed_at = time.time()
        self._executions[execution.execution_id] = execution
        
        # Sauvegarder l'historique
        self._save_execution(execution)
        
        return execution
    
    def _save_execution(self, execution: WorkflowExecution):
        """Sauvegarde une exécution dans l'historique."""
        history_file = self._executions_dir / "history.jsonl"
        try:
            with open(history_file, 'a') as f:
                f.write(json.dumps(execution.to_dict(), ensure_ascii=False) + '\n')
        except Exception as e:
            logger.error(f"Error saving execution: {e}")
    
    def get_execution(self, execution_id: str) -> Optional[dict]:
        """Récupère une exécution par son ID."""
        exec = self._executions.get(execution_id)
        return exec.to_dict() if exec else None
    
    def list_executions(self, workflow_id: str = None, limit: int = 50) -> list:
        """Liste les exécutions récentes."""
        execs = list(self._executions.values())
        if workflow_id:
            execs = [e for e in execs if e.workflow_id == workflow_id]
        execs.sort(key=lambda e: e.started_at, reverse=True)
        return [e.to_dict() for e in execs[:limit]]
