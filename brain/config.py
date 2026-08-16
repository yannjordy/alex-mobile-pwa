"""Configuration centralisée pour Alex Brain."""
import os

# Load .env
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# Modèle opencode par défaut (free)
OPENCODE_MODEL = os.environ.get("ALEX_OPENCODE_MODEL", "mimo-v2.5-free")

# Opencode instance dédiée à Alex (port 4097)
OPENCODE_API_URL = os.environ.get("ALEX_OPENCODE_API_URL", "http://127.0.0.1:4097")

# User
USER_NAME = os.environ.get("ALEX_USER_NAME", "Jordy")

# Limits
MAX_TOOL_RETRIES = 2
MAX_SESSIONS = 100
MAX_SESSION_MSGS = 30

# API Key pour authentification (vide = pas d'auth)
API_KEY = os.environ.get("ALEX_API_KEY", "")
