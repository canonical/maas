#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.configurations import (
    ConfigurationsRepository,
)
from maasservicelayer.models.configurations import Configuration
from maasservicelayer.services import ConfigurationsService


@pytest.mark.asyncio
class TestConfigurationsService:
    @pytest.mark.parametrize(
        "value",
        ["test", True, {"test": {"name": "myname", "age": 18}}, 1234, None],
    )
    async def test_get(self, value: Any) -> None:
        db_connection = Mock(AsyncConnection)
        configurations_repository_mock = Mock(ConfigurationsRepository)
        configurations_repository_mock.get.return_value = Configuration(
            id=1, name="test", value=value
        )
        configurations_service = ConfigurationsService(
            connection=db_connection,
            configurations_repository=configurations_repository_mock,
        )
        assert value == await configurations_service.get("test")

    async def test_unexisting_get(self) -> None:
        db_connection = Mock(AsyncConnection)
        configurations_repository_mock = Mock(ConfigurationsRepository)
        configurations_repository_mock.get.return_value = None
        configurations_service = ConfigurationsService(
            connection=db_connection,
            configurations_repository=configurations_repository_mock,
        )
        assert await configurations_service.get("test") is None
