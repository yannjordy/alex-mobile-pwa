"""Utilitaires pour Alex Brain."""
import re
import time
from typing import Optional


def estimate_complexity(message: str) -> int:
    """Score de complexité : 1=simple, 2=moyen, 3=complexe."""
    from .prompts import COMPLEXITY_WORDS
    msg = message.lower()
    words = re.findall(r'\w+', msg)
    score = 1
    for w in words:
        score += COMPLEXITY_WORDS.get(w, 0)
    msg_len = len(words)
    if msg_len > 30:
        score += 2
    elif msg_len > 15:
        score += 1
    return min(score, 5)


def is_polluted_conversation(text: str) -> bool:
    if not text:
        return False
    polluted = ["request timed out", "API Error", "Unable to connect", "error"]
    return any(p in text for p in polluted)
