# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

import pytest
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.configurations import (
    DatabaseConfigurationBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.database_configurations import (
    DatabaseConfigurationsRepository,
)
from tests.fixtures.factories.configuration import create_test_configuration
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestDatabaseConfigurationsRepository:
    @pytest.mark.parametrize(
        "value",
        ["test", True, {"test": {"name": "myname", "age": 18}}, 1234, None],
    )
    async def test_get(
        self, db_connection: AsyncConnection, fixture: Fixture, value: Any
    ) -> None:
        await create_test_configuration(
            fixture=fixture, name="test", value=value
        )
        database_configuration_repository = DatabaseConfigurationsRepository(
            Context(connection=db_connection)
        )
        configuration = await database_configuration_repository.get("test")
        assert value == configuration.value
        assert configuration.name == "test"

    async def test_unexisting_get(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        database_configuration_repository = DatabaseConfigurationsRepository(
            Context(connection=db_connection)
        )
        assert (
            await database_configuration_repository.get("whatever")
        ) is None

    async def test_create_or_update_new(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        database_configuration_repository = DatabaseConfigurationsRepository(
            Context(connection=db_connection)
        )
        await database_configuration_repository.create_or_update(
            DatabaseConfigurationBuilder(name="foo", value="bar")
        )
        dbconfig = await database_configuration_repository.get("foo")
        assert dbconfig.name == "foo"
        assert dbconfig.value == "bar"

    async def test_create_or_update_updated(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        database_configuration_repository = DatabaseConfigurationsRepository(
            Context(connection=db_connection)
        )
        created_dbconfig = (
            await database_configuration_repository.create_or_update(
                DatabaseConfigurationBuilder(name="foo", value="bar")
            )
        )
        updated_dbconfig = (
            await database_configuration_repository.create_or_update(
                DatabaseConfigurationBuilder(name="foo", value="newbar")
            )
        )

        assert created_dbconfig.id == updated_dbconfig.id
        assert created_dbconfig.name == updated_dbconfig.name
        assert updated_dbconfig.value == "newbar"

    async def test_clear(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_configuration(
            fixture=fixture, name="test1", value="value1"
        )
        await create_test_configuration(fixture=fixture, name="test2", value=2)
        database_configuration_repository = DatabaseConfigurationsRepository(
            Context(connection=db_connection)
        )
        await database_configuration_repository.clear()
        configurations = await database_configuration_repository.get_many(
            QuerySpec()
        )
        assert len(configurations) == 0

    async def test_set_many(self, db_connection: AsyncConnection) -> None:
        database_configuration_repository = DatabaseConfigurationsRepository(
            Context(connection=db_connection)
        )
        test_cfg = {"test1": "value1", "test2": 2}
        configuration = await database_configuration_repository.set_many(
            test_cfg
        )
        assert len(configuration) == 2
        assert configuration[0].name == "test1"
        assert configuration[0].value == "value1"
        assert configuration[1].name == "test2"
        assert configuration[1].value == 2
