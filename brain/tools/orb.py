"""Outil orb — change la forme de l'orb Alex en temps réel."""
import asyncio


SHAPES = [
    "question", "exclamation", "error", "headphones", "tv", "phone",
    "search", "google", "github", "star", "heart", "music", "camera",
    "lightbulb", "clock", "chat", "gear", "globe", "terminal", "boat",
    "mountain", "happy", "sad", "love", "thinking_face", "angry", "wow",
    "lightning", "shield", "rocket", "brain", "wand", "eye", "fire",
    "sparkles", "refresh", "download", "upload", "code", "chart",
    "compass", "lock", "wifi", "cloud", "bell", "map", "folder", "bug", "key",
]


def set_shape(shape: str = "sparkles", hold_ms: int = 5000):
    """Change la forme de l'orb Alex.

    Args:
        shape: Nom de la forme parmi la liste disponible
        hold_ms: Durée d'affichage en millisecondes (défaut 5000)
    """
    from ..routes import _broadcast_event

    if shape not in SHAPES:
        return f"Forme inconnue « {shape} ». Formes disponibles : {', '.join(SHAPES)}"

    asyncio.get_event_loop().create_task(
        _broadcast_event("shape_change", {"shape": shape, "hold_ms": hold_ms})
    )
    return f"Forme changée → {shape}"
