#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
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
