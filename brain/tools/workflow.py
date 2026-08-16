"""Gestionnaire de workflows multi-étapes pour Alex.

Permet d'exécuter des séquences d'opérations CLI en plusieurs étapes,
avec pause pour décision utilisateur et reprise automatique.

Exemples d'usage :
- Analyser un projet Supabase → puis déployer Docker → puis créer une issue GitHub
- Installer des dépendances → puis lancer un build → puis tester
- Scanner un projet → puis corriger les erreurs → puis commiter
"""

import asyncio
import time
import json
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_DECISION = "waiting_decision"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class WorkflowStep:
    id: str
    title: str
    command: Optional[str] = None
    func: Optional[Callable] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    status: StepStatus = StepStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    requires_confirmation: bool = True
    depends_on: Optional[str] = None  # id of previous step
    started_at: Optional[float] = None
    finished_at: Optional[float] = None


@dataclass
class Workflow:
    id: str
    title: str
    steps: list = field(default_factory=list)
    current_step_index: int = 0
    status: str = "running"  # running, paused, completed, failed, cancelled
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    context: dict = field(default_factory=dict)  # données partagées entre étapes
    on_step_complete: Optional[Callable] = None
    on_workflow_complete: Optional[Callable] = None


class WorkflowManager:
    """Gestionnaire central des workflows multi-étapes."""

    def __init__(self):
        self._workflows: dict[str, Workflow] = {}
        self._counter = 0

    def create_workflow(self, title: str, steps: list, context: dict = None) -> Workflow:
        """Crée un nouveau workflow avec des étapes prédéfinies."""
        self._counter += 1
        wf_id = f"wf-{self._counter}-{int(time.time())}"

        workflow = Workflow(
            id=wf_id,
            title=title,
            steps=steps,
            context=context or {}
        )
        self._workflows[wf_id] = workflow
        return workflow

    def get_workflow(self, wf_id: str) -> Optional[Workflow]:
        return self._workflows.get(wf_id)

    def list_active(self) -> list:
        """Liste les workflows actifs (en cours ou en attente)."""
        return [
            wf for wf in self._workflows.values()
            if wf.status in ("running", "paused")
        ]

    async def execute_step(self, wf_id: str, step_index: int = None) -> dict:
        """Exécute une étape du workflow. Retourne le résultat."""
        wf = self._workflows.get(wf_id)
        if not wf:
            return {"error": "Workflow introuvable"}

        if step_index is None:
            step_index = wf.current_step_index

        if step_index >= len(wf.steps):
            wf.status = "completed"
            return {"status": "completed", "message": "Toutes les étapes sont terminées"}

        step = wf.steps[step_index]
        step.status = StepStatus.RUNNING
        step.started_at = time.time()
        wf.updated_at = time.time()

        try:
            if step.func:
                result = await step.func(*step.args, **step.kwargs)
            elif step.command:
                result = await self._run_command(step.command)
            else:
                result = {"error": "Pas de commande ou de fonction définie"}

            step.status = StepStatus.COMPLETED
            step.result = result if isinstance(result, str) else json.dumps(result)
            step.finished_at = time.time()
            wf.current_step_index = step_index + 1
            wf.updated_at = time.time()

            # Stocker le résultat dans le contexte pour les étapes suivantes
            wf.context[f"step_{step.id}_result"] = step.result

            return {
                "status": "completed",
                "step_id": step.id,
                "result": step.result,
                "next_step": step_index + 1 < len(wf.steps)
            }

        except Exception as e:
            step.status = StepStatus.FAILED
            step.error = str(e)
            step.finished_at = time.time()
            wf.status = "failed"
            wf.updated_at = time.time()
            return {
                "status": "failed",
                "step_id": step.id,
                "error": str(e)
            }

    async def _run_command(self, command: str) -> str:
        """Exécute une commande shell et retourne la sortie."""
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=300)
        output = stdout.decode("utf-8", errors="replace")
        if proc.returncode != 0:
            error = stderr.decode("utf-8", errors="replace")
            raise Exception(f"Commande échouée (rc={proc.returncode}): {error[:500]}")
        return output

    def pause_workflow(self, wf_id: str, reason: str = "") -> bool:
        """Met en pause un workflow (en attente de décision)."""
        wf = self._workflows.get(wf_id)
        if not wf or wf.status != "running":
            return False
        wf.status = "paused"
        wf.updated_at = time.time()
        if wf.current_step_index < len(wf.steps):
            wf.steps[wf.current_step_index].status = StepStatus.WAITING_DECISION
        return True

    def resume_workflow(self, wf_id: str) -> bool:
        """Reprend un workflow en pause."""
        wf = self._workflows.get(wf_id)
        if not wf or wf.status != "paused":
            return False
        wf.status = "running"
        wf.updated_at = time.time()
        if wf.current_step_index < len(wf.steps):
            wf.steps[wf.current_step_index].status = StepStatus.PENDING
        return True

    def cancel_workflow(self, wf_id: str) -> bool:
        """Annule un workflow."""
        wf = self._workflows.get(wf_id)
        if not wf:
            return False
        wf.status = "cancelled"
        wf.updated_at = time.time()
        for step in wf.steps:
            if step.status in (StepStatus.PENDING, StepStatus.RUNNING, StepStatus.WAITING_DECISION):
                step.status = StepStatus.CANCELLED
        return True

    def skip_step(self, wf_id: str, step_index: int = None) -> bool:
        """Passe une étape."""
        wf = self._workflows.get(wf_id)
        if not wf:
            return False
        idx = step_index or wf.current_step_index
        if idx < len(wf.steps):
            wf.steps[idx].status = StepStatus.SKIPPED
            wf.current_step_index = idx + 1
            wf.updated_at = time.time()
            return True
        return False

    def get_status(self, wf_id: str) -> dict:
        """Retourne le statut détaillé d'un workflow."""
        wf = self._workflows.get(wf_id)
        if not wf:
            return {"error": "Workflow introuvable"}

        steps_status = []
        for i, step in enumerate(wf.steps):
            steps_status.append({
                "index": i,
                "id": step.id,
                "title": step.title,
                "status": step.status.value,
                "command": step.command,
                "result": step.result[:200] if step.result else None,
                "error": step.error[:200] if step.error else None,
                "duration": (step.finished_at - step.started_at) if step.finished_at and step.started_at else None
            })

        return {
            "id": wf.id,
            "title": wf.title,
            "status": wf.status,
            "current_step": wf.current_step_index,
            "total_steps": len(wf.steps),
            "steps": steps_status,
            "context": wf.context,
            "created_at": wf.created_at,
            "updated_at": wf.updated_at
        }

    def cleanup(self, max_age_seconds: int = 3600):
        """Supprime les workflows terminés depuis trop longtemps."""
        now = time.time()
        to_remove = []
        for wf_id, wf in self._workflows.items():
            if wf.status in ("completed", "cancelled", "failed"):
                if now - wf.updated_at > max_age_seconds:
                    to_remove.append(wf_id)
        for wf_id in to_remove:
            del self._workflows[wf_id]


# Instance globale
workflow_manager = WorkflowManager()


def create_step(id: str, title: str, command: str = None, func: Callable = None,
                args: tuple = (), kwargs: dict = None,
                requires_confirmation: bool = True, depends_on: str = None) -> WorkflowStep:
    """Helper pour créer une étape de workflow."""
    return WorkflowStep(
        id=id,
        title=title,
        command=command,
        func=func,
        args=args,
        kwargs=kwargs or {},
        requires_confirmation=requires_confirmation,
        depends_on=depends_on
    )
