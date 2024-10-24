from datetime import datetime
from ipaddress import IPv4Address
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
    StaticIPAddressResourceBuilder,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.staticipaddress import StaticIPAddressService


@pytest.mark.asyncio
class TestStaticIPAddressService:
    async def test_create_or_update(self) -> None:
        now = datetime.utcnow()
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            disabled_boot_architectures=[],
            rdns_mode=1,
            active_discovery=True,
            managed=True,
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
        repository_mock.create_or_update = AsyncMock(
            return_value=existing_ip_address
        )

        staticipaddress_service = StaticIPAddressService(
            Mock(AsyncConnection), repository_mock
        )

        resource = (
            StaticIPAddressResourceBuilder()
            .with_ip(IPv4Address("10.0.0.2"))
            .with_lease_time(60)
            .with_alloc_type(IpAddressType.DISCOVERED)
            .with_subnet_id(subnet.id)
            .with_created(now)
            .with_updated(now)
            .build()
        )
        updated_resource = await staticipaddress_service.create_or_update(
            resource
        )

        assert updated_resource == existing_ip_address
        repository_mock.create_or_update.assert_called_once_with(resource)

    async def test_get_discovered_ips_in_family_for_interfaces(self) -> None:
        now = datetime.utcnow()
        interface = Interface(
            id=1,
            name="eth0",
            type=InterfaceType.PHYSICAL,
            mac="00:11:22:33:44:55",
            created=now,
            updated=now,
        )

        repository_mock = Mock(StaticIPAddressRepository)

        staticipaddress_service = StaticIPAddressService(
            Mock(AsyncConnection), repository_mock
        )

        await staticipaddress_service.get_discovered_ips_in_family_for_interfaces(
            [interface]
        )

        repository_mock.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
