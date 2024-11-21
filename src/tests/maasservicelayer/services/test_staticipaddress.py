from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
    StaticIPAddressResourceBuilder,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from maastemporalworker.workflow.dhcp import ConfigureDHCPParam


@pytest.mark.asyncio
class TestStaticIPAddressService:
    async def test_create_or_update(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        existing_ip_address = StaticIPAddress(
            id=1,
            ip=IPv4Address("10.0.0.1"),
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=30,
            temp_expires_on=now,
            subnet_id=1,
            created=now,
            updated=now,
        )

        repository_mock = Mock(StaticIPAddressRepository)
        repository_mock.create_or_update.return_value = existing_ip_address

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=repository_mock,
        )

        await staticipaddress_service.create_or_update(
            StaticIPAddressResourceBuilder()
            .with_ip("10.0.0.2")
            .with_lease_time(30)
            .with_alloc_type(IpAddressType.DISCOVERED)
            .with_subnet_id(subnet.id)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        repository_mock.create_or_update.assert_called_once_with(
            (
                StaticIPAddressResourceBuilder()
                .with_ip("10.0.0.2")
                .with_lease_time(30)
                .with_alloc_type(IpAddressType.DISCOVERED)
                .with_subnet_id(subnet.id)
                .with_created(now)
                .with_updated(now)
                .build()
            )
        )

    async def test_create_or_update_registers_configure_dhcp(self):
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.create_or_update.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.create_or_update(
            StaticIPAddressResourceBuilder()
            .with_ip(sip.ip)
            .with_lease_time(sip.lease_time)
            .with_alloc_type(sip.alloc_type)
            .with_subnet_id(sip.subnet_id)
            .with_created(sip.created)
            .with_updated(sip.updated)
            .build()
        )

        mock_staticipaddress_repository.create_or_update.assert_called_once_with(
            (
                StaticIPAddressResourceBuilder()
                .with_ip(sip.ip)
                .with_lease_time(sip.lease_time)
                .with_alloc_type(sip.alloc_type)
                .with_subnet_id(sip.subnet_id)
                .with_created(sip.created)
                .with_updated(sip.updated)
                .build()
            ),
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                static_ip_addr_ids=[sip.id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_get_discovered_ips_in_family_for_interfaces(self) -> None:
        now = utcnow()
        interface = Interface(
            id=1,
            name="eth0",
            type=InterfaceType.PHYSICAL,
            mac="00:11:22:33:44:55",
            created=now,
            updated=now,
        )

        repository_mock = Mock(StaticIPAddressRepository)

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=repository_mock,
        )

        await staticipaddress_service.get_discovered_ips_in_family_for_interfaces(
            [interface]
        )

        repository_mock.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )

    async def test_create(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            vlan_id=1,
            managed=True,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.create.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.create(
            StaticIPAddressResourceBuilder()
            .with_ip(sip.ip)
            .with_lease_time(sip.lease_time)
            .with_alloc_type(sip.alloc_type)
            .with_subnet_id(sip.subnet_id)
            .with_created(sip.created)
            .with_updated(sip.updated)
            .build()
        )

        mock_staticipaddress_repository.create.assert_called_once_with(
            (
                StaticIPAddressResourceBuilder()
                .with_ip(sip.ip)
                .with_lease_time(sip.lease_time)
                .with_alloc_type(sip.alloc_type)
                .with_subnet_id(sip.subnet_id)
                .with_created(sip.created)
                .with_updated(sip.updated)
                .build()
            ),
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                static_ip_addr_ids=[sip.id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_update(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.update_by_id.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.update_by_id(
            sip.id,
            (
                StaticIPAddressResourceBuilder()
                .with_ip(sip.ip)
                .with_lease_time(sip.lease_time)
                .with_alloc_type(sip.alloc_type)
                .with_subnet_id(sip.subnet_id)
                .with_created(sip.created)
                .with_updated(sip.updated)
                .build()
            ),
        )

        mock_staticipaddress_repository.update_by_id.assert_called_once_with(
            sip.id,
            (
                StaticIPAddressResourceBuilder()
                .with_ip(sip.ip)
                .with_lease_time(sip.lease_time)
                .with_alloc_type(sip.alloc_type)
                .with_subnet_id(sip.subnet_id)
                .with_created(sip.created)
                .with_updated(sip.updated)
                .build()
            ),
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                static_ip_addr_ids=[sip.id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete(self) -> None:
        now = utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
            vlan_id=1,
            created=now,
            updated=now,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.2",
            lease_time=30,
            subnet_id=subnet.id,
            alloc_type=IpAddressType.AUTO,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)
        mock_staticipaddress_repository.get_by_id.return_value = sip

        mock_temporal = Mock(TemporalService)

        staticipaddress_service = StaticIPAddressService(
            context=Context(),
            temporal_service=mock_temporal,
            staticipaddress_repository=mock_staticipaddress_repository,
        )

        await staticipaddress_service.delete_by_id(
            id=sip.id,
        )

        mock_staticipaddress_repository.delete_by_id.assert_called_once_with(
            sip.id,
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(
                subnet_ids=[sip.subnet_id],
            ),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
