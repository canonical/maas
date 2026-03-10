#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import SwitchesService
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_SWITCH = Switch(
    id=1,
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
            staticipaddress_repository=Mock(StaticIPAddressRepository),
            staticipaddress_service=Mock(StaticIPAddressService),
            interfaces_service=Mock(InterfacesService),
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
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)
        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )
        assert service.repository == switches_repository

    async def test_get_switch_by_mac_address(self) -> None:
        """Test getting a switch by its management interface MAC address."""
        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)
        test_switch = Switch(
            id=1,
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
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
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
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)
        test_switch = Switch(
            id=1,
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
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )

        result = await service.check_installer_for_switch("00:11:22:33:44:55")

        assert result == 42
        interfaces_repository.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_with(id=test_switch.id)
        switches_repository.update_by_id.assert_called_once()

    async def test_create_switch_and_link_interface(self) -> None:
        """Test creating a switch and linking an existing interface.

        This should claim an UNKNOWN interface and convert it to PHYSICAL.
        """
        from maascommon.enums.interface import InterfaceType
        from maasservicelayer.models.interfaces import Interface

        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)
        test_switch = Switch(
            id=1,
            target_image_id=None,
            created=utcnow(),
            updated=utcnow(),
        )
        # The interface should be updated from UNKNOWN to PHYSICAL
        updated_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            switch_id=test_switch.id,
        )

        switches_repository.create.return_value = test_switch
        interfaces_service.link_interface_to_switch.return_value = (
            updated_interface
        )

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
            staticipaddress_repository=Mock(StaticIPAddressRepository),
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )

        from maasservicelayer.builders.switches import SwitchBuilder

        builder = SwitchBuilder()
        result = await service.create_switch_and_link_interface(
            builder, interface_id=10
        )

        assert result == test_switch
        switches_repository.create.assert_called_once()
        interfaces_service.link_interface_to_switch.assert_called_once_with(
            interface_id=10, switch_id=test_switch.id
        )

    async def test_post_delete_hook_with_no_interfaces(self) -> None:
        """Test post_delete_hook when switch has no interfaces."""

        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)

        # No interfaces for this switch
        interfaces_repository.get_many.return_value = []

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )

        # Should complete without any IP operations
        await service.post_delete_hook(TEST_SWITCH)

        interfaces_repository.get_many.assert_called_once()
        # No IP operations should be called
        staticipaddress_repository.get_ip_addresses_for_interface.assert_not_called()
        staticipaddress_repository.unlink_interface_from_ip.assert_not_called()
        staticipaddress_service.delete_by_id.assert_not_called()

    async def test_post_delete_hook_with_interface_own_ip(self) -> None:
        """Test post_delete_hook with interface having its own IP (not shared)."""
        from maascommon.enums.ipaddress import IpAddressType
        from maasservicelayer.models.interfaces import Interface
        from maasservicelayer.models.staticipaddress import StaticIPAddress

        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)

        # One interface with one IP
        test_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type="physical",
            enabled=True,
            params={},
            created=utcnow(),
            updated=utcnow(),
        )
        test_ip = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )

        interfaces_repository.get_many.return_value = [test_interface]
        staticipaddress_repository.get_ip_addresses_for_interface.return_value = [
            test_ip
        ]
        staticipaddress_repository.get_interface_count_for_ip.return_value = (
            0  # No more interfaces after unlinking
        )

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )

        await service.post_delete_hook(TEST_SWITCH)

        # Verify the flow: get interfaces → get IPs → unlink → check count → delete
        interfaces_repository.get_many.assert_called_once()
        staticipaddress_repository.get_ip_addresses_for_interface.assert_called_once_with(
            test_interface.id
        )
        staticipaddress_repository.unlink_interface_from_ip.assert_called_once_with(
            interface_id=test_interface.id,
            staticipaddress_id=test_ip.id,
        )
        staticipaddress_repository.get_interface_count_for_ip.assert_called_once_with(
            test_ip.id
        )
        staticipaddress_service.delete_by_id.assert_called_once_with(
            test_ip.id
        )

    async def test_post_delete_hook_with_shared_ip(self) -> None:
        """Test post_delete_hook with interface having a shared IP (not deleted)."""
        from maascommon.enums.ipaddress import IpAddressType
        from maasservicelayer.models.interfaces import Interface
        from maasservicelayer.models.staticipaddress import StaticIPAddress

        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)

        test_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type="physical",
            enabled=True,
            params={},
            created=utcnow(),
            updated=utcnow(),
        )
        test_ip = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )

        interfaces_repository.get_many.return_value = [test_interface]
        staticipaddress_repository.get_ip_addresses_for_interface.return_value = [
            test_ip
        ]
        staticipaddress_repository.get_interface_count_for_ip.return_value = (
            1  # Still has another interface
        )

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )

        await service.post_delete_hook(TEST_SWITCH)

        # IP should be unlinked but NOT deleted
        staticipaddress_repository.unlink_interface_from_ip.assert_called_once_with(
            interface_id=test_interface.id,
            staticipaddress_id=test_ip.id,
        )
        staticipaddress_repository.get_interface_count_for_ip.assert_called_once_with(
            test_ip.id
        )
        staticipaddress_service.delete_by_id.assert_not_called()

    async def test_post_delete_hook_with_multiple_interfaces_and_ips(
        self,
    ) -> None:
        """Test post_delete_hook with multiple interfaces and various IP scenarios."""
        from maascommon.enums.ipaddress import IpAddressType
        from maasservicelayer.models.interfaces import Interface
        from maasservicelayer.models.staticipaddress import StaticIPAddress

        interfaces_repository = Mock(InterfaceRepository)
        switches_repository = Mock(SwitchesRepository)
        staticipaddress_repository = Mock(StaticIPAddressRepository)
        staticipaddress_service = Mock(StaticIPAddressService)
        interfaces_service = Mock(InterfacesService)

        # Two interfaces
        interface1 = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type="physical",
            enabled=True,
            params={},
            created=utcnow(),
            updated=utcnow(),
        )
        interface2 = Interface(
            id=20,
            name="eth1",
            mac_address="00:11:22:33:44:66",
            type="physical",
            enabled=True,
            params={},
            created=utcnow(),
            updated=utcnow(),
        )

        # Three IPs with different sharing patterns
        ip1 = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )  # Only on interface1
        ip2 = StaticIPAddress(
            id=200,
            ip="192.168.1.20",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )  # Shared (will remain)
        ip3 = StaticIPAddress(
            id=300,
            ip="192.168.1.30",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )  # Only on interface2

        interfaces_repository.get_many.return_value = [interface1, interface2]

        # Setup IP associations
        def get_ips_for_interface(interface_id):
            if interface_id == 10:
                return [ip1, ip2]  # interface1 has ip1 and ip2
            elif interface_id == 20:
                return [ip3]  # interface2 has ip3
            return []

        staticipaddress_repository.get_ip_addresses_for_interface.side_effect = get_ips_for_interface

        # Setup interface counts after unlinking
        def get_interface_count(ip_id):
            if ip_id == 100:
                return 0  # ip1 orphaned
            elif ip_id == 200:
                return 1  # ip2 still shared with another interface
            elif ip_id == 300:
                return 0  # ip3 orphaned
            return 0

        staticipaddress_repository.get_interface_count_for_ip.side_effect = (
            get_interface_count
        )

        service = SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            interfaces_repository=interfaces_repository,
            staticipaddress_repository=staticipaddress_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
        )

        await service.post_delete_hook(TEST_SWITCH)

        # Verify all IPs were processed
        assert (
            staticipaddress_repository.get_ip_addresses_for_interface.call_count
            == 2
        )
        assert (
            staticipaddress_repository.unlink_interface_from_ip.call_count == 3
        )
        assert (
            staticipaddress_repository.get_interface_count_for_ip.call_count
            == 3
        )

        # Verify only orphaned IPs were deleted (ip1 and ip3, not ip2)
        assert staticipaddress_service.delete_by_id.call_count == 2
        deleted_ip_ids = [
            call[1]["id"] if call[1] else call[0][0]
            for call in staticipaddress_service.delete_by_id.call_args_list
        ]
        assert 100 in deleted_ip_ids  # ip1 deleted
        assert 300 in deleted_ip_ids  # ip3 deleted
        assert 200 not in deleted_ip_ids  # ip2 NOT deleted (still shared)
