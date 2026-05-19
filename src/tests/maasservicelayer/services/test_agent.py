# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.apiclient import MAASAPIClient
from maasservicelayer.context import Context
from maasservicelayer.services import (
    AgentsService,
    ConfigurationsService,
    UsersService,
)
from maasservicelayer.services.agents import AgentsServiceCache


@pytest.mark.asyncio
class TestAgentsService:
    async def test_get_service_configuration(self) -> None:
        agents_service = AgentsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
        )

        api_client = AsyncMock(spec=MAASAPIClient)
        api_client.url = "http://example.com"
        agents_service._apiclient = api_client

        await agents_service.get_service_configuration(
            system_id="agent", service_name="foo"
        )
        api_client.request_async.assert_called_with(
            method="GET",
            url="http://example.com/api/2.0/agents/agent/services/foo/config/",
        )

    async def test_get_apiclient(self) -> None:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        agents_service = AgentsService(
            context=Context(),
            configurations_service=configurations_service,
            users_service=users_service,
        )

        apiclient = await agents_service._get_apiclient()

        assert apiclient.url == "http://example.com"

    async def test_get_apiclient_is_cached(self) -> None:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        cache = AgentsServiceCache()
        agents_service = AgentsService(
            context=Context(),
            configurations_service=configurations_service,
            users_service=users_service,
            cache=cache,
        )

        apiclient = await agents_service._get_apiclient()
        assert apiclient.url == "http://example.com"
        configurations_service.get.assert_called_once()

        await agents_service._get_apiclient()
        configurations_service.get.assert_called_once()

        assert cache.api_client is not None
