import json
import os
from typing import Any, Optional
from cryptography.fernet import Fernet
from .settings import CONFIG_DIR, CONFIG_FILE, KEY_FILE

# Tentativo import cryptography per cifratura API Key (opzionale)
try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False


class ConfigManager:
    """Gestisce la persistenza delle configurazioni e la sicurezza della API Key."""

    _instance: Optional['ConfigManager'] = None

    def __new__(cls) -> 'ConfigManager':
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._config: dict[str, Any] = {}
        self._cipher: Optional[Fernet] = None

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._init_encryption()
        self._load_config()

    def _init_encryption(self) -> None:
        """Inizializza chiave di cifratura."""
        if not CRYPTO_AVAILABLE:
            return

        try:
            if KEY_FILE.exists():
                key = KEY_FILE.read_bytes()
            else:
                key = Fernet.generate_key()
                KEY_FILE.write_bytes(key)
                if os.name != 'nt':  # Non Windows
                    KEY_FILE.chmod(0o600)

            self._cipher = Fernet(key)
        except Exception:
            pass

    def _load_config(self) -> None:
        """Carica configurazione da file JSON."""
        if CONFIG_FILE.exists():
            try:
                self._config = json.loads(CONFIG_FILE.read_text(encoding='utf-8'))
            except Exception:
                self._config = {}

    def _save_config(self) -> None:
        """Salva configurazione su file JSON."""
        try:
            CONFIG_FILE.write_text(
                json.dumps(self._config, indent=2, ensure_ascii=False),
                encoding='utf-8'
            )
        except Exception:
            pass

    def get_api_key(self) -> str:
        """Recupera e decifra la API Key salvata."""
        encrypted_key = self._config.get('api_key', '')
        if not encrypted_key:
            return ''

        if self._cipher and CRYPTO_AVAILABLE:
            try:
                return self._cipher.decrypt(encrypted_key.encode()).decode()
            except Exception:
                return encrypted_key
        return encrypted_key

    def set_api_key(self, api_key: str) -> None:
        """Cifra e salva la API Key."""
        if self._cipher and CRYPTO_AVAILABLE:
            try:
                encrypted = self._cipher.encrypt(api_key.encode()).decode()
                self._config['api_key'] = encrypted
            except Exception:
                self._config['api_key'] = api_key
        else:
            self._config['api_key'] = api_key
        self._save_config()

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
        self._save_config()
