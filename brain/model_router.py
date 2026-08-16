"""Router de modèles LLM --route chaque requête au modèle optimal."""
import re
from enum import Enum
from typing import Optional


class TaskType(Enum):
    """Types de tâches pour le routing."""
    GREETING = "greeting"
    QUICK_QUESTION = "quick_question"
    CODE = "code"
    TOOL_CALL = "tool_call"
    ANALYSIS = "analysis"
    DOCUMENT = "document"
    CREATIVE = "creative"
    GENERAL = "general"


# Modèles disponibles (free)
MODELS = {
    "nemotron": "nemotron-3-ultra-free",      # Cerveau principal - analyse complexe
    "deepseek": "deepseek-v4-flash-free",     # Rapide - général, tools
    "mimo": "mimo-v2.5-free",                 # Code, raisonnement
    "longcat": "longcat-2.0-free",            # Documents longs
    "ling": "ling-3.0-tiny-free",             # Ultra-rapide, réponses courtes
}

# Mapping tâche → modèle
ROUTING_TABLE = {
    TaskType.GREETING: "ling",              # Salutations → ultra-rapide
    TaskType.QUICK_QUESTION: "deepseek",    # Questions rapides → deepseek
    TaskType.CODE: "mimo",                  # Code, Docker, sécurité, installations → mimo
    TaskType.TOOL_CALL: "deepseek",         # Tools → deepseek (respecte le format)
    TaskType.ANALYSIS: "nemotron",          # Analyse → nemotron (plus intelligent)
    TaskType.DOCUMENT: "longcat",           # Documents → longcat (contexte long)
    TaskType.CREATIVE: "nemotron",          # Créatif → nemotron
    TaskType.GENERAL: "deepseek",           # Général → deepseek (rapide)
}

# Patterns pour la classification
PATTERNS = {
    TaskType.GREETING: [
        r'^(salut|bonjour|coucou|hey|hello|bonsoir|bonne nuit|ça va|comment vas)',
        r'^(yo|hi|sup|wesh|wsh)',
    ],
    TaskType.CODE: [
        r'(code|coder|programm|fonction|class|import|def |async |await )',
        r'(bug|erreur|error|debug|fix|corrig)',
        r'(python|javascript|typescript|html|css|sql|bash|shell)',
        r'(git|github|commit|push|pull|merge|branch)',
        r'(api|endpoint|route|fastapi|flask|django)',
        r'(write_code|executer_test|git_)',
        r'(install|installer|apt|pip|npm|yarn|docker|dockerfile|compose)',
        r'(sécurité|security|firewall|ssh|keychain|mot de passe|password)',
        r'(extension|plugin|package|module|dependance)',
        r'(container|image|volume|network|docker)',
    ],
    TaskType.TOOL_CALL: [
        r'(lance|exécute|utilise|appelle|run|execute)',
        r'(batterie|volume|luminosité|wifi|bluetooth|alarme)',
        r'(fichier|dossier|lire|écrire|copier|déplacer|supprimer)',
        r'(recherche|chercher|trouver|search)',
        r'(météo|weather| météo)',
        r'(notification|notif|alerte)',
        r'(ouvre|ouvrir|lance|lancer|ferme|fermer)',
        r'(screenshot|capture|photo|image)',
        r'(processus|task|tuer|kill)',
    ],
    TaskType.ANALYSIS: [
        r'(analyse|analyser|explique|expliquer|pourquoi|comment ça marche)',
        r'(compar|différence|avantage|inconvénient)',
        r'(stratégie|plan|planifier|organiser)',
        r'(résumé|résumer|synthèse|summary)',
    ],
    TaskType.DOCUMENT: [
        r'(document|pdf|word|docx|texte long)',
        r'(resume|résumé|summarize|tl;dr)',
        r'(page|pages|chapitre|section)',
    ],
    TaskType.CREATIVE: [
        r'(écris|write|crée|create|invente|invent)',
        r'(histoire|story|poème|poem|chanson|song)',
        r'(idée|idea|concept|pitch)',
    ],
    TaskType.QUICK_QUESTION: [
        r'^(c\'est quoi|qu\'est-ce que|quel|quelle|combien|où|quand|qui)',
        r'^(how|what|where|when|who|why|which)',
        r'^(définition|definition|signifie|meaning)',
    ],
}


def classify_query(message: str) -> TaskType:
    """Classifie le type de requête."""
    msg_lower = message.lower().strip()

    # Vérifier les patterns par priorité
    for task_type, patterns in PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, msg_lower, re.IGNORECASE):
                return task_type

    # Par défaut
    return TaskType.GENERAL


def get_model_for_query(message: str) -> str:
    """Retourne le modèle optimal pour une requête donnée."""
    task_type = classify_query(message)
    model_key = ROUTING_TABLE.get(task_type, "deepseek")
    return MODELS[model_key]


def get_model_info(message: str) -> dict:
    """Retourne des infos détaillées sur le routing."""
    task_type = classify_query(message)
    model_key = ROUTING_TABLE.get(task_type, "deepseek")
    model_id = MODELS[model_key]
    return {
        "task_type": task_type.value,
        "model_key": model_key,
        "model_id": model_id,
        "reason": _get_reason(task_type),
    }


def _get_reason(task_type: TaskType) -> str:
    """Retourne une explication du choix."""
    reasons = {
        TaskType.GREETING: "Salutation → modèle ultra-rapide",
        TaskType.QUICK_QUESTION: "Question simple → deepseek rapide",
        TaskType.CODE: "Code/Docker/Sécurité → mimo (meilleur en technique)",
        TaskType.TOOL_CALL: "Outil → deepseek (respecte le format [[tool:...]])",
        TaskType.ANALYSIS: "Analyse → nemotron (plus intelligent)",
        TaskType.DOCUMENT: "Document → longcat (contexte long)",
        TaskType.CREATIVE: "Créatif → nemotron (plus créatif)",
        TaskType.GENERAL: "Général → deepseek (rapide et cohérent)",
    }
    return reasons.get(task_type, "Modèle par défaut")
