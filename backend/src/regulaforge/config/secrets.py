"""Provider-agnostic secrets management.

Supports multiple backends:

* ``env`` — environment variables / ``.env`` files (local development)
* ``aws`` — AWS Secrets Manager
* ``vault`` — HashiCorp Vault
* ``azure`` — Azure Key Vault

Usage::

    provider = get_secrets_provider()
    db_password = await provider.get("database/postgresql/password")
"""

from __future__ import annotations

import os
import threading
from abc import ABC, abstractmethod
from typing import Any, Optional, Protocol, Union

from pydantic import SecretStr


# ─── Abstract provider ───────────────────────────────────────────────────

class SecretsProvider(ABC):
    """Abstract base class for secrets providers."""

    @abstractmethod
    async def get(self, key: str) -> Optional[SecretStr]:
        """Retrieve a secret by its key.

        Args:
            key: Secret identifier (e.g. ``"database/postgresql/password"``).

        Returns:
            The secret value wrapped in ``SecretStr``, or ``None`` if not found.
        """
        ...

    @abstractmethod
    async def get_many(self, *keys: str) -> dict[str, Optional[SecretStr]]:
        """Retrieve multiple secrets at once.

        Default implementation calls ``get()`` sequentially.
        Override in subclasses for batch-fetch optimizations.
        """
        ...

    async def get_or_raise(self, key: str) -> SecretStr:
        """Like ``get()`` but raises ``KeyError`` if not found."""
        value = await self.get(key)
        if value is None:
            raise KeyError(f"Secret {key!r} not found")
        return value

    async def get_str(self, key: str, default: str = "") -> str:
        """Get secret as plain string with a fallback default."""
        value = await self.get(key)
        return value.get_secret_value() if value else default

    async def close(self) -> None:
        """Release any resources held by the provider."""
        ...


# ─── Environment variable provider ───────────────────────────────────────

class EnvSecretsProvider(SecretsProvider):
    """Secrets provider backed by environment variables / .env files.

    Resolves keys by converting ``"/"`` to ``"__"`` and uppercasing.
    Example: ``"database/postgresql/password"`` → ``DATABASE__POSTGRESQL__PASSWORD``.
    """

    def __init__(self, dotenv_path: Optional[str] = None) -> None:
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path)
        except ImportError:
            pass

    def _resolve_key(self, key: str) -> str:
        return key.upper().replace("/", "__").replace("-", "_")

    async def get(self, key: str) -> Optional[SecretStr]:
        env_key = self._resolve_key(key)
        value = os.getenv(env_key)
        if value is None:
            return None
        return SecretStr(value)

    async def get_many(self, *keys: str) -> dict[str, Optional[SecretStr]]:
        return {key: await self.get(key) for key in keys}


# ─── AWS Secrets Manager provider ────────────────────────────────────────

class AwsSecretsManagerProvider(SecretsProvider):
    """Secrets provider backed by AWS Secrets Manager.

    Requires ``boto3`` to be installed.
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        session: Optional[Any] = None,
    ) -> None:
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for AwsSecretsManagerProvider. "
                "Install with: pip install regulaforge[aws]"
            )
        self._client = (
            session.client("secretsmanager", region_name=region_name)
            if session
            else boto3.client("secretsmanager", region_name=region_name)
        )

    async def get(self, key: str) -> Optional[SecretStr]:
        try:
            import aioboto3
            session = aioboto3.Session()
            async with session.client(
                "secretsmanager",
                region_name=self._client.meta.region_name,
            ) as client:
                response = await client.get_secret_value(SecretId=key)
                return SecretStr(response["SecretString"])
        except ImportError:
            pass

        try:
            response = self._client.get_secret_value(SecretId=key)
            return SecretStr(response["SecretString"])
        except self._client.exceptions.ResourceNotFoundException:
            return None

    async def get_many(self, *keys: str) -> dict[str, Optional[SecretStr]]:
        return {key: await self.get(key) for key in keys}

    async def close(self) -> None:
        if hasattr(self, "_client"):
            self._client.close()


# ─── HashiCorp Vault provider ────────────────────────────────────────────

class VaultSecretsProvider(SecretsProvider):
    """Secrets provider backed by HashiCorp Vault (KV v2 engine).

    Requires ``hvac`` to be installed.
    """

    def __init__(
        self,
        url: str = "http://localhost:8200",
        token: Optional[str] = None,
        mount_point: str = "secret",
        **kwargs: Any,
    ) -> None:
        try:
            import hvac
        except ImportError:
            raise ImportError(
                "hvac is required for VaultSecretsProvider. "
                "Install with: pip install regulaforge[vault]"
            )
        self._client = hvac.Client(url=url, token=token, **kwargs)
        self._mount_point = mount_point
        if not self._client.is_authenticated():
            raise RuntimeError("Vault authentication failed")

    async def get(self, key: str) -> Optional[SecretStr]:
        try:
            response = self._client.secrets.kv.v2.read_secret_version(
                path=key,
                mount_point=self._mount_point,
            )
            data = response.get("data", {}).get("data", {})
            if not data:
                return None
            return SecretStr(str(data.get("value", data)))
        except Exception:
            return None

    async def get_many(self, *keys: str) -> dict[str, Optional[SecretStr]]:
        return {key: await self.get(key) for key in keys}


# ─── Azure Key Vault provider ────────────────────────────────────────────

class AzureKeyVaultProvider(SecretsProvider):
    """Secrets provider backed by Azure Key Vault.

    Requires ``azure-identity`` and ``azure-keyvault-secrets``.
    """

    def __init__(
        self,
        vault_url: str,
        credential: Optional[Any] = None,
    ) -> None:
        try:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
        except ImportError:
            raise ImportError(
                "azure-identity and azure-keyvault-secrets are required "
                "for AzureKeyVaultProvider. "
                "Install with: pip install regulaforge[azure]"
            )
        cred = credential or DefaultAzureCredential()
        self._client = SecretClient(vault_url=vault_url, credential=cred)

    async def get(self, key: str) -> Optional[SecretStr]:
        try:
            secret = self._client.get_secret(key)
            return SecretStr(secret.value)
        except Exception:
            return None

    async def get_many(self, *keys: str) -> dict[str, Optional[SecretStr]]:
        return {key: await self.get(key) for key in keys}

    async def close(self) -> None:
        self._client.close()


# ─── Factory (thread-safe) ───────────────────────────────────────────────

_PROVIDER_LOCK = threading.Lock()
_PROVIDER_CACHE: dict[str, SecretsProvider] = {}
_PROVIDER_CLASSES: dict[str, type[SecretsProvider]] = {
    "env": EnvSecretsProvider,
    "aws": AwsSecretsManagerProvider,
    "vault": VaultSecretsProvider,
    "azure": AzureKeyVaultProvider,
}


def get_secrets_provider(
    provider_name: Optional[str] = None,
    **kwargs: Any,
) -> SecretsProvider:
    """Thread-safe factory that returns a secrets provider by name.

    If *provider_name* is ``None``, reads the ``REGULAFORGE_SECRETS_PROVIDER``
    environment variable (defaults to ``"env"``).

    Providers are cached so only one instance is created per provider type
    per process.
    """
    name = provider_name or os.getenv("REGULAFORGE_SECRETS_PROVIDER", "env")

    instance = _PROVIDER_CACHE.get(name)
    if instance is not None:
        return instance

    cls = _PROVIDER_CLASSES.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown secrets provider: {name!r}. "
            f"Available: {', '.join(_PROVIDER_CLASSES)}"
        )

    with _PROVIDER_LOCK:
        instance = _PROVIDER_CACHE.get(name)
        if instance is None:
            instance = cls(**kwargs)
            _PROVIDER_CACHE[name] = instance
    return instance


# ─── Resolution utilities ────────────────────────────────────────────────

def resolve_secret_sync(
    value: str | SecretStr | None,
    provider: Optional[SecretsProvider] = None,
    *,
    default: Optional[str] = None,
) -> Optional[str]:
    """Synchronously resolve a value that may be a ``"secret://path"`` reference.

    For async contexts, prefer ``resolve_secret()``.
    """
    if value is None:
        return default

    if isinstance(value, SecretStr):
        return value.get_secret_value()

    if isinstance(value, str) and value.startswith("secret://"):
        if provider is None:
            raise RuntimeError(
                "SecretsProvider required to resolve secret references"
            )
        key = value[len("secret://"):]
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(provider.get_str(key), loop)
            resolved = future.result(timeout=30)
        else:
            resolved = asyncio.run(provider.get_str(key))
        return resolved or default

    return str(value)


async def resolve_secret(
    value: str | SecretStr | None,
    provider: Optional[SecretsProvider] = None,
    *,
    default: Optional[str] = None,
) -> Optional[str]:
    """Resolve a value that may be a ``"secret://path"`` reference.

    Prefer this async version in async contexts to avoid thread switching.
    """
    if value is None:
        return default

    if isinstance(value, SecretStr):
        return value.get_secret_value()

    if isinstance(value, str) and value.startswith("secret://"):
        if provider is None:
            raise RuntimeError(
                "SecretsProvider required to resolve secret references"
            )
        key = value[len("secret://"):]
        resolved = await provider.get_str(key)
        return resolved or default

    return str(value)


__all__ = [
    "SecretsProvider",
    "EnvSecretsProvider",
    "AwsSecretsManagerProvider",
    "VaultSecretsProvider",
    "AzureKeyVaultProvider",
    "get_secrets_provider",
    "resolve_secret",
    "resolve_secret_sync",
]
