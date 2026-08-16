"""Système de workflows/automatisations pour Alex — inspiré de n8n."""
from .engine import WorkflowEngine, Workflow, WorkflowNode, WorkflowConnection
from .nodes import NodeRegistry, BaseNode, TriggerNode, ActionNode, ConditionNode
from .credentials import CredentialManager

__all__ = [
    'WorkflowEngine', 'Workflow', 'WorkflowNode', 'WorkflowConnection',
    'NodeRegistry', 'BaseNode', 'TriggerNode', 'ActionNode', 'ConditionNode',
    'CredentialManager'
]
