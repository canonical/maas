# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from maascommon.apiclient import MAASAPIClient
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.rackcontrollers import (
    RackControllersRepository,
)
from maasservicelayer.models.rackcontrollers import RackController
from maasservicelayer.services import (
    ConfigurationsService,
    RackControllersService,
    UsersService,
)
from maasservicelayer.services.rackcontrollers import (
    RackControllersServiceCache,
)
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestRackControllersService:
    @pytest.fixture
    def test_instance(self) -> RackController:
        now = utcnow()
        return RackController(
            id=1,
            created=now,
            updated=now,
            uuid=str(uuid4()),
            rack_id=1,
            node_id=1,
        )

    async def test_get_service_configuration(self) -> None:
        rack_controllers_service = RackControllersService(
            context=Context(),
            repository=Mock(RackControllersRepository),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
        )

        api_client = AsyncMock(spec=MAASAPIClient)
        api_client.url = "http://example.com"
        rack_controllers_service._apiclient = api_client

        await rack_controllers_service.get_service_configuration(
            system_id="rack_controller", service_name="foo"
        )
        api_client.request_async.assert_called_with(
            method="GET",
            url="http://example.com/api/2.0/rackcontrollers/rack_controller/services/foo/config/",
        )

    async def test_get_apiclient(self) -> None:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        rack_controllers_service = RackControllersService(
            context=Context(),
            repository=Mock(RackControllersRepository),
            configurations_service=configurations_service,
            users_service=users_service,
        )

        apiclient = await rack_controllers_service._get_apiclient()

        assert apiclient.url == "http://example.com"

    async def test_get_apiclient_is_cached(self) -> None:
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        cache = RackControllersServiceCache()
        rack_controllers_service = RackControllersService(
            context=Context(),
            repository=Mock(RackControllersRepository),
            configurations_service=configurations_service,
            users_service=users_service,
            cache=cache,
        )

        apiclient = await rack_controllers_service._get_apiclient()
        assert apiclient.url == "http://example.com"
        configurations_service.get.assert_called_once()

        await rack_controllers_service._get_apiclient()
        configurations_service.get.assert_called_once()

        assert cache.api_client is not None

    async def test_delete(self, test_instance):
        rack_controller = test_instance

        repository_mock = Mock(RackControllersRepository)
        repository_mock.get_one.return_value = rack_controller
        repository_mock.delete_by_id.return_value = rack_controller
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        rack_controllers_service = RackControllersService(
            context=Context(),
            repository=repository_mock,
            configurations_service=configurations_service,
            users_service=users_service,
        )

        query = Mock(QuerySpec)
        await rack_controllers_service.delete_one(query)

        repository_mock.delete_by_id.assert_called_once_with(
            id=rack_controller.id
        )

    async def test_delete_many(self, test_instance):
        rack_controller1 = test_instance
        rack_controller2 = RackController(
            id=2,
            created=rack_controller1.created,
            updated=rack_controller1.updated,
            uuid="mock-uuid",
            rack_id=2,
            node_id=2,
        )
        rack_controllers = [rack_controller1, rack_controller2]

        repository_mock = Mock(RackControllersRepository)
        repository_mock.get_many.return_value = rack_controllers
        repository_mock.delete_many.return_value = rack_controllers
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "http://example.com"
        users_service = Mock(UsersService)
        users_service.get_MAAS_user_apikey.return_value = "key:token:secret"

        rack_controllers_service = RackControllersService(
            context=Context(),
            repository=repository_mock,
            configurations_service=configurations_service,
            users_service=users_service,
        )

        query = Mock(QuerySpec)
        await rack_controllers_service.delete_many(query)

        repository_mock.delete_many.assert_called_once_with(query=query)
