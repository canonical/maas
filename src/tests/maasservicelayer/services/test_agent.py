#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.services import (
    AgentsService,
    ConfigurationsService,
    UsersService,
)


@pytest.mark.asyncio
class TestAgentsService:
    async def test_get_service_configuration(self) -> None:
        db_connection = Mock(AsyncConnection)
        configurations_service = Mock(ConfigurationsService)
        users_service = Mock(UsersService)

        agents_service = AgentsService(
            db_connection,
            configurations_service=configurations_service,
            users_service=users_service,
        )

        api_client = AsyncMock()
        agents_service._apiclient = api_client

        await agents_service.get_service_configuration(
            system_id="agent", service_name="foo"
        )
        api_client.request.assert_called_with(
            method="GET", path="agents/agent/services/foo/config/"
        )

    async def test_get_apiclient(self) -> None:
        db_connection = Mock(AsyncConnection)
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_user_apikeys.return_value = ["key:token:secret"]

        agents_service = AgentsService(
            db_connection,
            configurations_service=configurations_service,
            users_service=users_service,
        )

        apiclient = await agents_service._get_apiclient()

        assert apiclient.base_url == "http://example.com/api/2.0/"
