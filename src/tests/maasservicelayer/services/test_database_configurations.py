# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any
from unittest.mock import Mock

import pytest

from maasservicelayer.builders.configurations import (
    DatabaseConfigurationBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.database_configurations import (
    DatabaseConfigurationsRepository,
)
from maasservicelayer.models.configurations import DatabaseConfiguration
from maasservicelayer.services.database_configurations import (
    DatabaseConfigurationNotFound,
    DatabaseConfigurationsService,
)


@pytest.mark.asyncio
class TestDatabaseConfigurationsService:
    @pytest.mark.parametrize(
        "value",
        ["test", True, {"test": {"name": "myname", "age": 18}}, 1234, None],
    )
    async def test_get(self, value: Any) -> None:
        database_configurations_repository_mock = Mock(
            DatabaseConfigurationsRepository
        )
        database_configurations_repository_mock.get.return_value = (
            DatabaseConfiguration(id=1, name="test", value=value)
        )
        database_configurations_service = DatabaseConfigurationsService(
            context=Context(),
            database_configurations_repository=database_configurations_repository_mock,
        )
        assert value == await database_configurations_service.get("test")

    async def test_unexisting_get(self) -> None:
        database_configurations_repository_mock = Mock(
            DatabaseConfigurationsRepository
        )
        database_configurations_repository_mock.get.return_value = None
        configurations_service = DatabaseConfigurationsService(
            context=Context(),
            database_configurations_repository=database_configurations_repository_mock,
        )
        with pytest.raises(DatabaseConfigurationNotFound):
            await configurations_service.get("test")

    async def test_create_or_update(self) -> None:
        database_configurations_repository_mock = Mock(
            DatabaseConfigurationsRepository
        )
        expected_dbconfig = DatabaseConfiguration(
            id=1, name="foo", value="bar"
        )
        database_configurations_repository_mock.create_or_update.return_value = expected_dbconfig
        configurations_service = DatabaseConfigurationsService(
            context=Context(),
            database_configurations_repository=database_configurations_repository_mock,
        )
        builder = DatabaseConfigurationBuilder(name="foo", value="bar")
        dbconfig = await configurations_service.create_or_update(builder)
        database_configurations_repository_mock.create_or_update.assert_awaited_once_with(
            builder
        )
        assert dbconfig == expected_dbconfig

    async def test_clear_and_set_many(self) -> None:
        database_configurations_repository_mock = Mock(
            DatabaseConfigurationsRepository
        )
        configurations_service = DatabaseConfigurationsService(
            context=Context(),
            database_configurations_repository=database_configurations_repository_mock,
        )
        test_cfg = {"theme": "dark"}
        await configurations_service.clear_and_set_many(test_cfg)
        database_configurations_repository_mock.clear.assert_called_once()
        database_configurations_repository_mock.set_many.assert_called_once_with(
            test_cfg
        )
