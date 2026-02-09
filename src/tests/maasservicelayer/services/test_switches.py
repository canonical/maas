#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.switches import SwitchStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import SwitchesService
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_SWITCH = Switch(
    id=1,
    status=SwitchStatus.NEW,
    target_image_id=None,
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestCommonSwitchesService(ServiceCommonTests):
    """Common tests for SwitchesService."""

    @pytest.fixture
    def service_instance(self) -> BaseService:
        return SwitchesService(
            context=Context(),
            switches_repository=Mock(SwitchesRepository),
            interfaces_repository=Mock(InterfaceRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_SWITCH


@pytest.mark.asyncio
class TestSwitchesService:
    """Specific tests for SwitchesService business logic."""

    async def test_service_initialization(self) -> None:
        """Test that the service can be initialized properly."""
        switches_repository = Mock(SwitchesRepository)
        interfaces_repository = Mock(InterfaceRepository)
        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
        )
        assert service.repository == switches_repository

    async def test_get_switch_by_mac_address(self) -> None:
        """Test getting a switch by its management interface MAC address."""
        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        test_switch = Switch(
            id=1,
            status=SwitchStatus.NEW,
            target_image_id=None,
            created=utcnow(),
            updated=utcnow(),
        )
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        interfaces_repository.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
        )

        result = await service.get_switch_by_mac_address("00:11:22:33:44:55")

        assert result == test_switch
        interfaces_repository.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_once_with(
            id=test_switch.id
        )

    async def test_get_installer_for_switch(self) -> None:
        """Test checking for an assigned NOS installer for a switch."""
        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        test_switch = Switch(
            id=1,
            status=SwitchStatus.NEW,
            target_image_id=42,
            created=utcnow(),
            updated=utcnow(),
        )
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        interfaces_repository.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
        )

        result = await service.check_installer_for_switch("00:11:22:33:44:55")

        assert result == 42
        interfaces_repository.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_with(id=test_switch.id)
        switches_repository.update_by_id.assert_called_once()
