from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.temporal import TemporalService


@pytest.mark.asyncio
class TestInterfacesService:
    async def test_get_interfaces_in_fabric(self):
        temporal_service_mock = Mock(TemporalService)

        interface_repository_mock = Mock(InterfaceRepository)

        interfaces_service = InterfacesService(
            context=Context(),
            temporal_service=temporal_service_mock,
            interface_repository=interface_repository_mock,
        )

        await interfaces_service.get_interfaces_in_fabric(fabric_id=0)

        interface_repository_mock.get_interfaces_in_fabric.assert_called_once_with(
            fabric_id=0
        )
