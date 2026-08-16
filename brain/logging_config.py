"""Système de logging pour Alex Brain."""
import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO"):
    """Configure le logging pour Alex Brain."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_dir / "alex.log", encoding="utf-8"),
        ],
    )

    # Réduire le bruit des libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger nommé."""
    return logging.getLogger(f"alex.{name}")
