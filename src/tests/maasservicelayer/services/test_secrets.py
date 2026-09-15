# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import abc
from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.secrets import (
    SecretsRepository,
    VaultSecretsRepository,
)
from maasservicelayer.models.configurations import VaultEnabledConfig
from maasservicelayer.models.secrets import (
    NodeDeployMetadataSecret,
    NodePowerParametersSecret,
    Secret,
    SecretModel,
    TLSSecret,
    VaultSecret,
    VCenterPasswordSecret,
)
from maasservicelayer.services.database_configurations import (
    DatabaseConfigurationNotFound,
    DatabaseConfigurationsService,
)
from maasservicelayer.services.secrets import (
    LocalSecretsStorageService,
    SecretNotFound,
    SecretsService,
    SecretsServiceCache,
    SecretsServiceFactory,
    VaultSecretsService,
)
from maasservicelayer.utils.date import utcnow
from maasservicelayer.vault.api.apiclient import AsyncVaultApiClient
from maasservicelayer.vault.api.models.exceptions import VaultNotFoundException
from maasservicelayer.vault.manager import AsyncVaultManager


@pytest.fixture(autouse=True)
def prepare():
    # Always reset the SecretsServiceFactory cache
    SecretsServiceFactory.clear()
    yield
    SecretsServiceFactory.clear()


@pytest.mark.asyncio
class SecretsServiceTestSuite:
    DEFAULT_SECRET = "secret"
    DEFAULT_COMPOSITE_SECRET = {"data": {"drivers": [1, 2, 3], "maps": True}}
    DEFAULT_MODEL = VCenterPasswordSecret()

    @abc.abstractmethod
    def get_secrets_service(self) -> SecretsService:
        pass

    # simple secrets
    async def test_get_not_path_not_found(self) -> None:
        secrets_service = self.get_secrets_service()
        with pytest.raises(SecretNotFound):
            await secrets_service.get_simple_secret(self.DEFAULT_MODEL)

    async def test_get_returns_default_if_path_not_found(self) -> None:
        secrets_service = self.get_secrets_service()
        retrieved_secret = await secrets_service.get_simple_secret(
            self.DEFAULT_MODEL, default=self.DEFAULT_SECRET
        )
        assert retrieved_secret == self.DEFAULT_SECRET

    @pytest.mark.parametrize(
        "model",
        [
            NodeDeployMetadataSecret(id=1),
            NodePowerParametersSecret(id=1),
            VCenterPasswordSecret(),
            TLSSecret(),
        ],
    )
    async def test_set_and_get_simple_secret(self, model: SecretModel) -> None:
        secrets_service = self.get_secrets_service()
        await secrets_service.set_simple_secret(model, self.DEFAULT_SECRET)
        retrieved_secret = await secrets_service.get_simple_secret(model)
        assert retrieved_secret == self.DEFAULT_SECRET

    @pytest.mark.parametrize(
        "model",
        [
            NodeDeployMetadataSecret(id=1),
            NodePowerParametersSecret(id=1),
            VCenterPasswordSecret(),
            TLSSecret(),
        ],
    )
    async def test_set_updates_simple_secret(self, model: SecretModel) -> None:
        updated_secret = "supersecret"
        secrets_service = self.get_secrets_service()
        await secrets_service.set_simple_secret(model, self.DEFAULT_SECRET)
        await secrets_service.set_simple_secret(model, updated_secret)
        retrieved_secret = await secrets_service.get_simple_secret(model)
        assert retrieved_secret == updated_secret

    # composite secrets
    async def test_get_composite_secret_path_not_found(self) -> None:
        secrets_service = self.get_secrets_service()
        with pytest.raises(SecretNotFound):
            await secrets_service.get_composite_secret(self.DEFAULT_MODEL)

    async def test_get_composite_secret_returns_default_if_path_not_found(
        self,
    ) -> None:
        secrets_service = self.get_secrets_service()
        retrieved_secret = await secrets_service.get_composite_secret(
            self.DEFAULT_MODEL, default=self.DEFAULT_COMPOSITE_SECRET
        )
        assert retrieved_secret == self.DEFAULT_COMPOSITE_SECRET

    @pytest.mark.parametrize(
        "model",
        [
            NodeDeployMetadataSecret(id=1),
            NodePowerParametersSecret(id=1),
            VCenterPasswordSecret(),
            TLSSecret(),
        ],
    )
    async def test_set_and_get_composite_secret(
        self, model: SecretModel
    ) -> None:
        secrets_service = self.get_secrets_service()
        await secrets_service.set_composite_secret(
            model, self.DEFAULT_COMPOSITE_SECRET
        )
        retrieved_secret = await secrets_service.get_composite_secret(model)
        assert retrieved_secret == self.DEFAULT_COMPOSITE_SECRET

    @pytest.mark.parametrize(
        "model",
        [
            NodeDeployMetadataSecret(id=1),
            NodePowerParametersSecret(id=1),
            VCenterPasswordSecret(),
            TLSSecret(),
        ],
    )
    async def test_set_updates_composite_secret(
        self, model: SecretModel
    ) -> None:
        updated_secret = {"mynewdata": [1, 2, 3, 4]}
        secrets_service = self.get_secrets_service()
        await secrets_service.set_composite_secret(
            model, self.DEFAULT_COMPOSITE_SECRET
        )
        await secrets_service.set_composite_secret(model, updated_secret)
        retrieved_secret = await secrets_service.get_composite_secret(model)
        assert retrieved_secret == updated_secret

    # delete
    @pytest.mark.parametrize(
        "model",
        [
            NodeDeployMetadataSecret(id=1),
            NodePowerParametersSecret(id=1),
            VCenterPasswordSecret(),
            TLSSecret(),
        ],
    )
    async def test_delete(self, model: SecretModel) -> None:
        secrets_service = self.get_secrets_service()
        await secrets_service.set_composite_secret(
            model, self.DEFAULT_COMPOSITE_SECRET
        )
        retrieved_secret = await secrets_service.get_composite_secret(model)
        assert retrieved_secret is not None
        await secrets_service.delete(model)
        with pytest.raises(SecretNotFound):
            await secrets_service.get_composite_secret(model)


class SecretsRepositoryMock(SecretsRepository):
    def __init__(self, context: Context):
        super().__init__(context)
        self.storage = {}

    async def create_or_update(self, path: str, value: dict[str, Any]) -> None:
        now = utcnow()
        secret = Secret(path=path, created=now, updated=now, value=value)
        self.storage[path] = secret

    async def get(self, path: str) -> Secret | None:
        return self.storage.get(path)

    async def delete(self, path: str) -> None:
        del self.storage[path]


class TestLocalSecretStorageService(SecretsServiceTestSuite):
    def get_secrets_service(self) -> SecretsService:
        connection = Mock(AsyncConnection)
        context = Context(connection=connection)
        return LocalSecretsStorageService(
            context, secrets_repository=SecretsRepositoryMock(context)
        )


class AsyncVaultManagerMock(AsyncVaultManager):
    def __init__(self):
        super().__init__(
            Mock(AsyncVaultApiClient), "role_id", "secret_id", "base_path"
        )
        self.storage = {}

    async def set(self, path: str, value: dict[str, Any]) -> None:
        self.storage[self._build_path_key(path)] = value

    async def get(self, path: str) -> dict[str, Any]:
        key = self._build_path_key(path)
        if key not in self.storage:
            raise VaultNotFoundException("Not found")
        return self.storage[key]

    async def delete(self, path: str) -> None:
        del self.storage[self._build_path_key(path)]

    def _build_path_key(self, path: str):
        return f"/v1/{self._secrets_mount}/data/{path}"


class VaultSecretsRepositoryMock(VaultSecretsRepository):
    def __init__(self, context: Context):
        super().__init__(context)
        self.storage = {}

    async def create_or_update(self, path: str) -> None:
        self.storage[path] = False

    async def get(self, path: str) -> VaultSecret | None:
        if path not in self.storage:
            return None
        return VaultSecret(path=path, deleted=self.storage[path])

    async def mark_deleted(self, path: str) -> None:
        if path in self.storage:
            self.storage[path] = True


@pytest.mark.asyncio
class TestVaultSecretService(SecretsServiceTestSuite):
    def get_secrets_service(self) -> SecretsService:
        connection = Mock(AsyncConnection)
        context = Context(connection=connection)
        return VaultSecretsService(
            context=context,
            cache=SecretsServiceCache(vault_manager=AsyncVaultManagerMock()),
            vault_secrets_repository=VaultSecretsRepositoryMock(context),
        )

    # delete only marks the secret for deletion in the VaultSecret table: it
    # is not removed from Vault immediately (a recurrent cleanup job does that
    # asynchronously). Override the base test to reflect this behaviour.
    @pytest.mark.parametrize(
        "model",
        [
            NodeDeployMetadataSecret(id=1),
            NodePowerParametersSecret(id=1),
            VCenterPasswordSecret(),
            TLSSecret(),
        ],
    )
    async def test_delete(self, model: SecretModel) -> None:
        secrets_service = self.get_secrets_service()
        await secrets_service.set_composite_secret(
            model, self.DEFAULT_COMPOSITE_SECRET
        )
        path = model.get_secret_path()
        repository = secrets_service.vault_secrets_repository
        assert repository.storage[path] is False

        await secrets_service.delete(model)

        # The secret is only marked for deletion in the VaultSecret table.
        assert repository.storage[path] is True
        # Even though the value is still physically in Vault, a secret marked
        # for deletion is not returned anymore.
        with pytest.raises(SecretNotFound):
            await secrets_service.get_composite_secret(model)

    async def test_vault_manager_is_cached(self, mocker):
        connection = Mock(AsyncConnection)
        context = Context(connection=connection)
        repository = VaultSecretsRepositoryMock(context)
        await repository.create_or_update(self.DEFAULT_MODEL.get_secret_path())
        secrets_service = VaultSecretsService(
            context=context,
            cache=SecretsServiceCache(),
            vault_secrets_repository=repository,
        )

        get_region_vault_manager_mock = mocker.patch(
            "maasservicelayer.services.secrets.get_region_vault_manager",
            return_value=AsyncVaultManagerMock(),
        )

        await secrets_service.get_simple_secret(
            self.DEFAULT_MODEL, default=self.DEFAULT_SECRET
        )
        get_region_vault_manager_mock.assert_called_once()

        await secrets_service.get_simple_secret(
            self.DEFAULT_MODEL, default=self.DEFAULT_SECRET
        )
        # Should have been cached
        get_region_vault_manager_mock.assert_called_once()


@pytest.mark.asyncio
class TestSecretServiceFactory:
    async def test_with_default_settings(self) -> None:
        db_connection = Mock(AsyncConnection)
        context = Context(connection=db_connection)
        database_configuration_service_mock = Mock(
            DatabaseConfigurationsService
        )
        database_configuration_service_mock.get.side_effect = (
            DatabaseConfigurationNotFound(VaultEnabledConfig.name)
        )
        assert SecretsServiceFactory.IS_VAULT_ENABLED is None
        secrets_service = await SecretsServiceFactory.produce(
            context, database_configuration_service_mock
        )
        assert SecretsServiceFactory.IS_VAULT_ENABLED is False
        assert isinstance(secrets_service, LocalSecretsStorageService)

    async def test_with_vault_enabled(self) -> None:
        db_connection = Mock(AsyncConnection)
        context = Context(connection=db_connection)
        database_configuration_service_mock = Mock(
            DatabaseConfigurationsService
        )
        database_configuration_service_mock.get.return_value = True
        secrets_service = await SecretsServiceFactory.produce(
            context, database_configuration_service_mock
        )
        assert SecretsServiceFactory.IS_VAULT_ENABLED is True
        assert isinstance(secrets_service, VaultSecretsService)

    async def test_with_vault_disabled(self) -> None:
        db_connection = Mock(AsyncConnection)
        context = Context(connection=db_connection)
        database_configuration_service_mock = Mock(
            DatabaseConfigurationsService
        )
        database_configuration_service_mock.get.return_value = False
        secrets_service = await SecretsServiceFactory.produce(
            context, database_configuration_service_mock
        )
        assert SecretsServiceFactory.IS_VAULT_ENABLED is False
        assert isinstance(secrets_service, LocalSecretsStorageService)

    async def test_clear(self) -> None:
        db_connection = Mock(AsyncConnection)
        context = Context(connection=db_connection)
        database_configuration_service_mock = Mock(
            DatabaseConfigurationsService
        )
        database_configuration_service_mock.get.return_value = False
        await SecretsServiceFactory.produce(
            context, database_configuration_service_mock
        )
        assert SecretsServiceFactory.IS_VAULT_ENABLED is False
        SecretsServiceFactory.clear()
        assert SecretsServiceFactory.IS_VAULT_ENABLED is None
