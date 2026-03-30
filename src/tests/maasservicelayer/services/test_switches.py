#  Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import SwitchesService
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.utils.date import utcnow

TEST_SWITCH = Switch(
    id=1,
    target_image_id=None,
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestSwitchesService:
    """Specific tests for SwitchesService business logic."""

    @pytest.fixture
    async def switches_repository(self):
        return Mock(SwitchesRepository)

    @pytest.fixture
    async def staticipaddress_service(self):
        return Mock(StaticIPAddressService)

    @pytest.fixture
    async def interfaces_service(self):
        return Mock(InterfacesService)

    @pytest.fixture
    async def service(
        self, switches_repository, staticipaddress_service, interfaces_service
    ):
        return SwitchesService(
            context=Context(),
            switches_repository=switches_repository,
            staticipaddress_service=staticipaddress_service,
            interfaces_service=interfaces_service,
            boot_resources_service=Mock(BootResourceService),
            boot_resource_sets_service=Mock(BootResourceSetsService),
            boot_resource_files_service=Mock(BootResourceFilesService),
        )

    async def test_get_switch_by_mac_address(
        self,
        service,
        switches_repository,
        interfaces_service,
    ) -> None:
        """Test getting a switch by its management interface MAC address."""
        test_switch = TEST_SWITCH
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        interfaces_service.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch

        result = await service.get_switch_by_mac_address("00:11:22:33:44:55")

        assert result == test_switch
        interfaces_service.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_once_with(
            id=test_switch.id
        )

    async def test_check_installer_for_switch(
        self,
        service,
        switches_repository,
        interfaces_service,
    ) -> None:
        """Test checking for an assigned NOS installer for a switch."""
        test_switch = TEST_SWITCH
        test_interface = Mock()
        test_interface.switch_id = test_switch.id

        interfaces_service.get_one.return_value = test_interface
        switches_repository.get_by_id.return_value = test_switch

        result = await service.check_installer_for_switch("00:11:22:33:44:55")

        assert result == 42
        interfaces_service.get_one.assert_called_once()
        switches_repository.get_by_id.assert_called_with(id=test_switch.id)

    async def test_create_switch_and_link_interface(
        self,
        service,
        switches_repository,
        interfaces_service,
    ) -> None:
        """Test creating a switch and linking an existing interface.

        This should claim an UNKNOWN interface and convert it to PHYSICAL.
        """
        test_switch = TEST_SWITCH
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

        builder = SwitchBuilder()
        result = await service.create_switch_and_link_interface(
            builder, interface_id=10
        )

        assert result == test_switch
        switches_repository.create.assert_called_once()
        interfaces_service.link_interface_to_switch.assert_called_once_with(
            interface_id=10, switch_id=test_switch.id
        )

    async def test_post_delete_hook_with_no_interfaces(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test post_delete_hook when switch has no interfaces."""
        # No interfaces for this switch
        interfaces_service.get_many.return_value = []

        # Should complete without any IP operations
        await service.post_delete_hook(TEST_SWITCH)

        interfaces_service.get_many.assert_called_once()
        # No IP operations should be called
        staticipaddress_service.get_ip_addresses_for_interface.assert_not_called()
        interfaces_service.unlink_interface_from_ips.assert_not_called()
        staticipaddress_service.delete_by_id.assert_not_called()

    async def test_post_delete_hook_with_interface_own_ip(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test post_delete_hook with interface having its own IP (not shared)."""
        # One interface with one IP
        test_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
        )
        test_ip = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )

        interfaces_service.get_many.return_value = [test_interface]
        staticipaddress_service.get_ip_addresses_for_interface.return_value = [
            test_ip
        ]
        staticipaddress_service.delete_ip_if_no_linked_interfaces.return_value = 0  # No more interfaces after unlinking

        await service.post_delete_hook(TEST_SWITCH)

        # Verify the flow: get interfaces → get IPs → unlink → check count → delete
        interfaces_service.get_many.assert_called_once()
        staticipaddress_service.get_ip_addresses_for_interface.assert_called_once_with(
            test_interface.id
        )
        interfaces_service.unlink_interface_from_ips.assert_called_once_with(
            interface_id=test_interface.id,
            staticipaddress_ids=[test_ip.id],
        )
        staticipaddress_service.delete_ip_if_no_linked_interfaces.assert_called_once_with(
            test_ip.id
        )
        staticipaddress_service.delete_by_id.assert_not_called()

    async def test_post_delete_hook_with_shared_ip(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test post_delete_hook with interface having a shared IP (not deleted)."""
        test_interface = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
        )
        test_ip = StaticIPAddress(
            id=100,
            ip="192.168.1.10",
            alloc_type=IpAddressType.AUTO,
            lease_time=0,
        )

        interfaces_service.get_many.return_value = [test_interface]
        staticipaddress_service.get_ip_addresses_for_interface.return_value = [
            test_ip
        ]
        staticipaddress_service.delete_ip_if_no_linked_interfaces.return_value = 1  # Still has another interface

        await service.post_delete_hook(TEST_SWITCH)

        # IP should be unlinked but NOT deleted
        interfaces_service.unlink_interface_from_ips.assert_called_once_with(
            interface_id=test_interface.id,
            staticipaddress_ids=[test_ip.id],
        )
        staticipaddress_service.delete_ip_if_no_linked_interfaces.assert_called_once_with(
            test_ip.id
        )
        staticipaddress_service.delete_by_id.assert_not_called()

    async def test_post_delete_hook_with_multiple_interfaces_and_ips(
        self,
        service,
        interfaces_service,
        staticipaddress_service,
    ) -> None:
        """Test post_delete_hook with multiple interfaces and various IP scenarios."""
        # Two interfaces
        interface1 = Interface(
            id=10,
            name="eth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            enabled=True,
            created=utcnow(),
            updated=utcnow(),
        )
        interface2 = Interface(
            id=20,
            name="eth1",
            mac_address="00:11:22:33:44:66",
            type=InterfaceType.PHYSICAL,
            enabled=True,
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

        interfaces_service.get_many.return_value = [interface1, interface2]

        # Setup IP associations
        def get_ips_for_interface(interface_id):
            if interface_id == 10:
                return [ip1, ip2]  # interface1 has ip1 and ip2
            elif interface_id == 20:
                return [ip3]  # interface2 has ip3
            return []

        staticipaddress_service.get_ip_addresses_for_interface.side_effect = (
            get_ips_for_interface
        )

        # Setup interface counts after unlinking
        def get_interface_count(ip_id):
            if ip_id == 100:
                return 0  # ip1 orphaned
            elif ip_id == 200:
                return 1  # ip2 still shared with another interface
            elif ip_id == 300:
                return 0  # ip3 orphaned
            return 0

        staticipaddress_service.delete_ip_if_no_linked_interfaces.side_effect = get_interface_count

        await service.post_delete_hook(TEST_SWITCH)

        # Verify all IPs were processed
        assert (
            staticipaddress_service.get_ip_addresses_for_interface.call_count
            == 2
        )
        assert interfaces_service.unlink_interface_from_ips.call_count == 2
        assert (
            staticipaddress_service.delete_ip_if_no_linked_interfaces.call_count
            == 3
        )

        # Deletion of orphaned static IPs is handled in repository logic.
        staticipaddress_service.delete_by_id.assert_not_called()
