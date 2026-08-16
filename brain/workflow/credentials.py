"""Gestionnaire de credentials pour les intégrations Alex — inspiré de n8n."""
import json
import os
import base64
import hashlib
import secrets
from typing import Any, Optional
from pathlib import Path
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)

class AuthType(str):
    """Types d'authentification supportés."""
    API_KEY = "api_key"
    BEARER = "bearer"
    OAUTH2 = "oauth2"
    BASIC = "basic"

@dataclass
class CredentialDefinition:
    """Définition d'un type de credential."""
    name: str
    auth_type: str  # api_key, bearer, oauth2, basic
    description: str = ""
    fields: list = field(default_factory=list)  # Champs requis
    auth_url: str = ""   # URL d'autorisation OAuth2
    token_url: str = ""  # URL de token OAuth2
    scopes: list = field(default_factory=list)  # Scopes OAuth2
    
    def to_dict(self):
        return asdict(self)

@dataclass
class Credential:
    """Un credential stocké."""
    id: str
    name: str
    app: str
    auth_type: str
    data: dict = field(default_factory=dict)  # Données chiffrées/chiffrées
    created_at: float = 0
    updated_at: float = 0
    
    def to_dict(self, mask: bool = True):
        d = asdict(self)
        if mask and 'data' in d:
            d['data'] = self._mask_data(d['data'])
        return d
    
    def _mask_data(self, data: dict) -> dict:
        """Masque les données sensibles."""
        masked = {}
        for key, value in data.items():
            if isinstance(value, str) and len(value) > 8:
                masked[key] = value[:4] + "****" + value[-4:]
            else:
                masked[key] = "****"
        return masked

# Définitions des credentials pour chaque intégration
CREDENTIAL_DEFINITIONS = {
    "gmail": CredentialDefinition(
        name="Gmail",
        auth_type=AuthType.OAUTH2,
        description="Connecter Gmail pour envoyer/lire des emails",
        fields=["client_id", "client_secret", "refresh_token"],
        auth_url="https://accounts.google.com/o/oauth2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/gmail.send", "https://www.googleapis.com/auth/gmail.readonly"]
    ),
    "google_drive": CredentialDefinition(
        name="Google Drive",
        auth_type=AuthType.OAUTH2,
        description="Connecter Google Drive pour gérer les fichiers",
        fields=["client_id", "client_secret", "refresh_token"],
        auth_url="https://accounts.google.com/o/oauth2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/drive"]
    ),
    "google_calendar": CredentialDefinition(
        name="Google Calendar",
        auth_type=AuthType.OAUTH2,
        description="Connecter Google Calendar pour gérer les événements",
        fields=["client_id", "client_secret", "refresh_token"],
        auth_url="https://accounts.google.com/o/oauth2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=["https://www.googleapis.com/auth/calendar"]
    ),
    "slack": CredentialDefinition(
        name="Slack",
        auth_type=AuthType.BEARER,
        description="Connecter Slack pour envoyer des messages",
        fields=["token"],
        auth_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        scopes=["chat:write", "channels:read"]
    ),
    "github": CredentialDefinition(
        name="GitHub",
        auth_type=AuthType.API_KEY,
        description="Connecter GitHub pour gérer les repos",
        fields=["token"],
        auth_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        scopes=["repo", "read:user"]
    ),
    "telegram": CredentialDefinition(
        name="Telegram",
        auth_type=AuthType.API_KEY,
        description="Connecter Telegram pour envoyer des messages",
        fields=["bot_token", "chat_id"]
    ),
    "discord": CredentialDefinition(
        name="Discord",
        auth_type=AuthType.BEARER,
        description="Connecter Discord pour envoyer des messages",
        fields=["bot_token"],
        auth_url="https://discord.com/api/oauth2/authorize",
        scopes=["bot", "messages.send"]
    ),
    "notion": CredentialDefinition(
        name="Notion",
        auth_type=AuthType.BEARER,
        description="Connecter Notion pour gérer les pages",
        fields=["api_key"],
        auth_url="https://api.notion.com/v1/oauth/authorize",
        scopes=["read_content", "insert_content"]
    ),
    "spotify": CredentialDefinition(
        name="Spotify",
        auth_type=AuthType.OAUTH2,
        description="Connecter Spotify pour la musique",
        fields=["client_id", "client_secret", "refresh_token"],
        auth_url="https://accounts.spotify.com/authorize",
        token_url="https://accounts.spotify.com/api/token",
        scopes=["user-read-playback-state", "user-modify-playback-state"]
    ),
    "openai": CredentialDefinition(
        name="OpenAI",
        auth_type=AuthType.API_KEY,
        description="Connecter OpenAI pour l'IA",
        fields=["api_key"]
    )
}


class CredentialManager:
    """Gestionnaire de credentials sécurisé."""
    
    def __init__(self):
        self._credentials: dict[str, Credential] = {}
        self._data_dir = Path(__file__).parent.parent.parent / "data"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._credentials_file = self._data_dir / "credentials.json"
        self._encryption_key = self._load_or_create_encryption_key()
        self._load_credentials()
    
    def _load_or_create_encryption_key(self) -> str:
        """Charge ou crée la clé de chiffrement."""
        key_file = self._data_dir / ".encryption_key"
        if key_file.exists():
            return key_file.read_text().strip()
        key = secrets.token_hex(32)
        key_file.write_text(key)
        os.chmod(key_file, 0o600)
        return key
    
    def _encrypt(self, data: str) -> str:
        """Chiffre les données (simplifié — en prod utiliser Fernet)."""
        # XOR simple pour démo — utiliser cryptography en prod
        key = self._encryption_key.encode()
        encrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(data.encode())])
        return base64.b64encode(encrypted).decode()
    
    def _decrypt(self, data: str) -> str:
        """Déchiffre les données."""
        key = self._encryption_key.encode()
        decoded = base64.b64decode(data)
        decrypted = bytes([b ^ key[i % len(key)] for i, b in enumerate(decoded)])
        return decrypted.decode()
    
    def _load_credentials(self):
        """Charge les credentials depuis le fichier."""
        if self._credentials_file.exists():
            try:
                with open(self._credentials_file, 'r') as f:
                    data = json.load(f)
                    for cred_data in data.get('credentials', []):
                        cred = Credential(
                            id=cred_data['id'],
                            name=cred_data['name'],
                            app=cred_data['app'],
                            auth_type=cred_data['auth_type'],
                            data={k: self._decrypt(v) for k, v in cred_data.get('data', {}).items()},
                            created_at=cred_data.get('created_at', 0),
                            updated_at=cred_data.get('updated_at', 0)
                        )
                        self._credentials[cred.id] = cred
                logger.info(f"Loaded {len(self._credentials)} credentials")
            except Exception as e:
                logger.error(f"Error loading credentials: {e}")
    
    def _save_credentials(self):
        """Sauvegarde les credentials sur le disque."""
        try:
            data = {
                'credentials': [
                    {
                        'id': c.id,
                        'name': c.name,
                        'app': c.app,
                        'auth_type': c.auth_type,
                        'data': {k: self._encrypt(v) for k, v in c.data.items()},
                        'created_at': c.created_at,
                        'updated_at': c.updated_at
                    }
                    for c in self._credentials.values()
                ]
            }
            with open(self._credentials_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving credentials: {e}")
    
    def list_credential_types(self) -> list:
        """Liste les types de credentials disponibles."""
        return [c.to_dict() for c in CREDENTIAL_DEFINITIONS.values()]
    
    def create_credential(self, name: str, app: str, auth_type: str, data: dict) -> Credential:
        """Crée un nouveau credential."""
        import time
        cred = Credential(
            id=f"cred_{secrets.token_hex(8)}",
            name=name,
            app=app,
            auth_type=auth_type,
            data=data,
            created_at=time.time(),
            updated_at=time.time()
        )
        self._credentials[cred.id] = cred
        self._save_credentials()
        return cred
    
    def get_credential(self, credential_id: str, mask: bool = True) -> Optional[dict]:
        """Récupère un credential."""
        cred = self._credentials.get(credential_id)
        return cred.to_dict(mask=mask) if cred else None
    
    def get_credential_data(self, credential_id: str) -> Optional[dict]:
        """Récupère les données déchiffrées d'un credential (usage interne)."""
        cred = self._credentials.get(credential_id)
        return cred.data if cred else None
    
    def list_credentials(self, app: str = None) -> list:
        """Liste les credentials."""
        creds = list(self._credentials.values())
        if app:
            creds = [c for c in creds if c.app == app]
        return [c.to_dict(mask=True) for c in creds]
    
    def update_credential(self, credential_id: str, **kwargs) -> Optional[Credential]:
        """Met à jour un credential."""
        import time
        cred = self._credentials.get(credential_id)
        if not cred:
            return None
        for key, value in kwargs.items():
            if key == 'data':
                cred.data.update(value)
            elif hasattr(cred, key):
                setattr(cred, key, value)
        cred.updated_at = time.time()
        self._save_credentials()
        return cred
    
    def delete_credential(self, credential_id: str) -> bool:
        """Supprime un credential."""
        if credential_id in self._credentials:
            del self._credentials[credential_id]
            self._save_credentials()
            return True
        return False
    
    def get_auth_headers(self, credential_id: str) -> dict:
        """Retourne les headers d'authentification pour un credential."""
        cred = self._credentials.get(credential_id)
        if not cred:
            return {}
        
        if cred.auth_type == AuthType.API_KEY:
            token = cred.data.get('token') or cred.data.get('api_key', '')
            return {"Authorization": f"token {token}"}
        elif cred.auth_type == AuthType.BEARER:
            token = cred.data.get('token') or cred.data.get('bot_token', '')
            return {"Authorization": f"Bearer {token}"}
        elif cred.auth_type == AuthType.OAUTH2:
            token = cred.data.get('access_token', '')
            return {"Authorization": f"Bearer {token}"}
        elif cred.auth_type == AuthType.BASIC:
            username = cred.data.get('username', '')
            password = cred.data.get('password', '')
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            return {"Authorization": f"Basic {encoded}"}
        
        return {}
