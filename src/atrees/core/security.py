"""
Security utilities for ATREES.

Provides encryption, key management, and secure storage for sensitive data.
"""

import base64
import json
import secrets
from typing import Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from pydantic import SecretStr

from atrees.config import get_settings


class EncryptionManager:
    """Manages encryption/decryption using Fernet authenticated encryption (AES-128-CBC plus HMAC-SHA256)."""

    def __init__(self, master_key: SecretStr | None = None):
        settings = get_settings()
        self.master_key = master_key or settings.ENCRYPTION_KEY
        self._fernet: Fernet | None = None

    @property
    def fernet(self) -> Fernet:
        """Lazy initialization of Fernet cipher."""
        if self._fernet is None:
            key_bytes = base64.b64decode(self.master_key.get_secret_value())
            if len(key_bytes) != 32:
                raise ValueError("Master key must be 32 bytes")
            # Fernet expects 32-byte key base64 encoded
            fernet_key = base64.urlsafe_b64encode(key_bytes)
            self._fernet = Fernet(fernet_key)
        return self._fernet

    def encrypt(self, data: str) -> str:
        """Encrypt a string and return base64-encoded ciphertext."""
        if not data:
            return ""
        encrypted = self.fernet.encrypt(data.encode("utf-8"))
        return base64.b64encode(encrypted).decode("ascii")

    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64-encoded ciphertext to string."""
        if not encrypted_data:
            return ""
        try:
            ciphertext = base64.b64decode(encrypted_data.encode("ascii"))
            decrypted = self.fernet.decrypt(ciphertext)
            return decrypted.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def encrypt_json(self, data: dict[str, Any]) -> str:
        """Encrypt a JSON-serializable dict."""
        json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        return self.encrypt(json_str)

    def decrypt_json(self, encrypted_data: str) -> dict[str, Any]:
        """Decrypt to JSON dict."""
        if not encrypted_data:
            return {}
        json_str = self.decrypt(encrypted_data)
        return json.loads(json_str)

    def rotate_key(self, new_master_key: SecretStr) -> dict[str, str]:
        """
        Generate re-encryption mapping for key rotation.
        Returns dict of {old_encrypted: new_encrypted} for all stored values.
        This is a utility for migration scripts.
        """
        old_fernet = self.fernet
        new_key_bytes = base64.b64decode(new_master_key.get_secret_value())
        new_fernet = Fernet(base64.urlsafe_b64encode(new_key_bytes))

        # This would be used in a migration script to re-encrypt all values
        # Implementation depends on storage backend
        raise NotImplementedError("Use migration script for key rotation")


def generate_encryption_key() -> str:
    """Generate a new 32-byte encryption key (base64 encoded)."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def generate_api_key() -> str:
    """Generate a new API key (32 bytes base64)."""
    return base64.b64encode(secrets.token_bytes(32)).decode("ascii")


def derive_key_from_password(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """
    Derive encryption key from password using PBKDF2.
    Returns (key, salt) where key is 32 bytes for AES-256.
    """
    if salt is None:
        salt = secrets.token_bytes(16)

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    key = kdf.derive(password.encode("utf-8"))
    return key, salt


def verify_password(password: str, salt: bytes, key: bytes) -> bool:
    """Verify a password against stored key and salt."""
    try:
        derived_key, _ = derive_key_from_password(password, salt)
        return secrets.compare_digest(derived_key, key)
    except Exception:
        return False


class SecretManager:
    """
    High-level secret management for storing/retrieving encrypted secrets in database.
    """

    def __init__(self, encryption_manager: EncryptionManager | None = None):
        self.encryption = encryption_manager or EncryptionManager()

    def store_secret(self, value: str) -> str:
        """Encrypt and return a secret for storage."""
        return self.encryption.encrypt(value)

    def retrieve_secret(self, encrypted_value: str) -> str:
        """Decrypt a stored secret."""
        return self.encryption.decrypt(encrypted_value)

    def store_json_secret(self, value: dict[str, Any]) -> str:
        """Encrypt and return a JSON secret for storage."""
        return self.encryption.encrypt_json(value)

    def retrieve_json_secret(self, encrypted_value: str) -> dict[str, Any]:
        """Decrypt a stored JSON secret."""
        return self.encryption.decrypt_json(encrypted_value)


# Column type for SQLAlchemy encrypted JSON storage
class EncryptedJSON:
    """
    SQLAlchemy type for encrypted JSON columns.
    Usage:
        config = Column(EncryptedJSON, default={})
    """

    def __init__(self):
        self.encryption = EncryptionManager()

    def process_bind_param(self, value: dict[str, Any] | None, dialect) -> str | None:
        if value is None:
            return None
        return self.encryption.encrypt_json(value)

    def process_result_value(self, value: str | None, dialect) -> dict[str, Any]:
        if value is None:
            return {}
        return self.encryption.decrypt_json(value)


class EncryptedString:
    """SQLAlchemy type for encrypted string columns."""

    def __init__(self):
        self.encryption = EncryptionManager()

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self.encryption.encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return self.encryption.decrypt(value)


# Input sanitization for prompt injection prevention
INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions?",
    r"disregard\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"forget\s+(everything|above|previous)",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+(if\s+you\s+are\s+)?",
    r"system\s*:",
    r"assistant\s*:",
    r"###\s*(instruction|system|prompt)",
    r"<\|.*?\|>",  # Special tokens
    r"\[INST\].*?\[/INST\]",  # Llama format
    r"<<SYS>>.*?<</SYS>>",  # System prompt injection
]


def sanitize_untrusted_input(text: str, max_length: int = 10000) -> str:
    """
    Sanitize untrusted input to prevent prompt injection.

    Args:
        text: Input text from untrusted source (messages, emails, web pages)
        max_length: Maximum allowed length (truncates if longer)

    Returns:
        Sanitized text safe for inclusion in AI prompts
    """
    if not text:
        return ""

    # Truncate
    if len(text) > max_length:
        text = text[:max_length] + "... [TRUNCATED]"

    # Remove potential injection patterns
    import re
    for pattern in INJECTION_PATTERNS:
        text = re.sub(pattern, "[FILTERED]", text, flags=re.IGNORECASE)

    return text


def sanitize_for_logging(data: dict[str, Any], sensitive_keys: list[str] | None = None) -> dict[str, Any]:
    """
    Remove sensitive fields from data before logging.

    Args:
        data: Dictionary to sanitize
        sensitive_keys: Additional keys to redact (default: common secret keys)

    Returns:
        Sanitized copy of the dictionary
    """
    if sensitive_keys is None:
        sensitive_keys = [
            "password", "secret", "token", "key", "api_key", "access_token",
            "refresh_token", "session", "cookie", "authorization", "auth",
            "credential", "private", "ssn", "credit_card", "cvv",
        ]

    result = {}
    for k, v in data.items():
        if any(sk in k.lower() for sk in sensitive_keys):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = sanitize_for_logging(v, sensitive_keys)
        elif isinstance(v, list):
            result[k] = [
                sanitize_for_logging(item, sensitive_keys) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[k] = v
    return result