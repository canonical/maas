from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.v3.db.configurations import ConfigurationsRepository
from maasapiserver.v3.models.configurations import Configuration
from maasapiserver.v3.services import ConfigurationsService


@pytest.mark.asyncio
class ConfigurationsServiceTestSuite:
    @pytest.mark.parametrize(
        "value",
        ["test", True, {"test": {"name": "myname", "age": 18}}, 1234, None],
    )
    async def test_get(self, value: Any) -> None:
        db_connection = Mock(AsyncConnection)
        configurations_repository_mock = Mock(ConfigurationsRepository)
        configurations_repository_mock.get = AsyncMock(
            return_value=Configuration(id=1, name="test", value=value)
        )
        configurations_service = ConfigurationsService(
            connection=db_connection,
            configurations_repository=configurations_repository_mock,
        )
        assert value == configurations_service.get("test")

    async def test_unexisting_get(self) -> None:
        db_connection = Mock(AsyncConnection)
        configurations_repository_mock = Mock(ConfigurationsRepository)
        configurations_repository_mock.get = AsyncMock(return_value=None)
        configurations_service = ConfigurationsService(
            connection=db_connection,
            configurations_repository=configurations_repository_mock,
        )
        assert configurations_service.get("test") is None
