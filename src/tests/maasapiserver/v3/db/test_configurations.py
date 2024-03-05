from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.configurations import ConfigurationsRepository
from tests.fixtures.factories.configuration import create_test_configuration
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestConfigurationsRepository:
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
        configuration_repository = ConfigurationsRepository(db_connection)
        configuration = await configuration_repository.get("test")
        assert value == configuration.value
        assert "test" == configuration.name

    async def test_unexisting_get(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        configuration_repository = ConfigurationsRepository(db_connection)
        assert None == (await configuration_repository.get("whatever"))
