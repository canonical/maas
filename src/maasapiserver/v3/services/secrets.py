import abc
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.secrets import SecretsRepository
from maasapiserver.v3.services.configurations import ConfigurationsService

UNSET = object()


# This is a duplicate of maasserver/secrets.py as it would import django runtime here
class SecretNotFound(Exception):
    """Raised when a secret is not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Secret '{path}' not found")


class SecretsService(Service, abc.ABC):
    """
    Abstract base class for managing secrets.
    This class defines the interface for managing secrets, both composite secrets (dict-like structures)
    and simple secrets (single values). It provides abstract methods for setting, getting, and deleting secrets.
    """

    SIMPLE_SECRET_KEY = "secret"

    @abc.abstractmethod
    async def set_composite_secret(
        self, path: str, value: dict[str, Any]
    ) -> None:
        """Create or update a composite secret."""
        pass

    @abc.abstractmethod
    async def set_simple_secret(self, path: str, value: Any) -> None:
        """Create or update a simple secret."""
        pass

    @abc.abstractmethod
    async def delete(self, path: str) -> None:
        """Delete a secret."""
        pass

    # This abstraction comes from the legacy django application. Keep it until we don't move away and we can refactor the
    # existing secrets to a proper structure.
    @abc.abstractmethod
    async def get_composite_secret(
        self, path: str, default: Any = UNSET
    ) -> Any:
        """Return the value for a composite secret."""
        pass

    async def get_simple_secret(self, path: str, default: Any = UNSET) -> Any:
        """Return the value for a simple secret."""
        try:
            secret = await self.get_composite_secret(path)
        except SecretNotFound:
            if default is UNSET:
                raise
            return default
        return secret[self.SIMPLE_SECRET_KEY]


class LocalSecretsStorageService(SecretsService):
    """Service to store and retrieve secrets from the database."""

    def __init__(
        self,
        connection: AsyncConnection,
        secrets_repository: SecretsRepository | None = None,
    ):
        super().__init__(connection)
        self.secrets_repository = (
            secrets_repository
            if secrets_repository
            else SecretsRepository(connection)
        )

    async def set_composite_secret(
        self, path: str, value: dict[str, Any]
    ) -> None:
        return await self.secrets_repository.create_or_update(path, value)

    async def set_simple_secret(self, path: str, value: Any) -> None:
        await self.set_composite_secret(
            path, value={self.SIMPLE_SECRET_KEY: value}
        )

    async def delete(self, path: str) -> None:
        return await self.secrets_repository.delete(path)

    async def get_composite_secret(
        self, path: str, default: Any = UNSET
    ) -> Any:
        secret = await self.secrets_repository.get(path)
        if not secret:
            if default is UNSET:
                raise SecretNotFound(path)
            return default
        return secret.value


class VaultSecretsService(SecretsService):
    """TODO: https://warthogs.atlassian.net/browse/MAASENG-2803 Just a placeholder at the moment"""

    async def set_composite_secret(
        self, path: str, value: dict[str, Any]
    ) -> None:
        raise Exception("Not implemented yet.")

    async def set_simple_secret(self, path: str, value: Any) -> None:
        raise Exception("Not implemented yet.")

    async def delete(self, path: str) -> None:
        raise Exception("Not implemented yet.")

    async def get_composite_secret(
        self, path: str, default: Any = UNSET
    ) -> Any:
        raise Exception("Not implemented yet.")


class SecretsServiceFactory:
    """
    A factory class to produce a SecretService based on the configuration settings.
    This factory class is responsible for creating the appropriate `SecretService` implementation
    based on the configuration settings related to the usage of Vault for secret management.
    The factory reads the configuration only once and caches the result for future requests.
    """

    VAULT_CONFIG_NAME = "vault_enabled"
    IS_VAULT_ENABLED = None

    @classmethod
    async def produce(
        cls, connection: AsyncConnection, config_service: ConfigurationsService
    ) -> (SecretsService):
        """
        Produce a `SecretService` based on the configuration settings.
        This method checks if Vault integration is enabled by reading the configuration from the database.
        If the `IS_VAULT_ENABLED` class-level variable is not yet set, it will query the configuration table
        through the provided `connection` to determine whether Vault integration should be used or not.
        Note:
        -----
        The factory caches the result of whether Vault integration is enabled or not,
        and subsequent calls to this method will return the cached result for performance reasons.
        If the application configuration changes, a cleanup of the cache or a restart of the application
        is required to re-evaluate the Vault settings.
        """
        if cls.IS_VAULT_ENABLED is None:
            result = await config_service.get(cls.VAULT_CONFIG_NAME)
            cls.IS_VAULT_ENABLED = result if result else False
        if cls.IS_VAULT_ENABLED:
            return VaultSecretsService(connection=connection)
        return LocalSecretsStorageService(connection=connection)

    @classmethod
    def clear(cls) -> None:
        """
        Clear the cached configuration, allowing the factory to re-evaluate Vault settings.
        This method clears the cached `IS_VAULT_ENABLED` variable, allowing the factory to re-evaluate
        the Vault settings when the next `produce` method is called.
        """
        cls.IS_VAULT_ENABLED = None
