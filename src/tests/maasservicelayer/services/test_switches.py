#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import SwitchesService
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_SWITCH = Switch(
    id=1,
    name="test-switch",
    mac_address="00:11:22:33:44:55",
    ip_address="192.168.1.100",
    model="Cisco Catalyst 2960",
    manufacturer="Cisco",
    description="Test network switch",
    vlan_id=1,
    subnet_id=1,
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
        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
        )
        assert service.repository == switches_repository
