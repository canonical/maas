from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
    StaticIPAddressResourceBuilder,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.staticipaddress import StaticIPAddressService


@pytest.mark.asyncio
class TestStaticIPAddressService:
    async def test_create_or_update_create(
        self, db_connection: AsyncConnection
    ) -> None:
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

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)

        staticipaddress_service = StaticIPAddressService(
            db_connection, mock_staticipaddress_repository
        )

        await staticipaddress_service.create_or_update(
            ip="10.0.0.2",
            lease_time=30,
            alloc_type=IpAddressType.DISCOVERED,
            subnet_id=subnet.id,
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository.create.assert_called_once_with(
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

    async def test_create_or_update_update(
        self, db_connection: AsyncConnection
    ) -> None:
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

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)

        staticipaddress_service = StaticIPAddressService(
            db_connection, mock_staticipaddress_repository
        )

        await staticipaddress_service.create_or_update(
            ip="10.0.0.2",
            lease_time=30,
            alloc_type=IpAddressType.DISCOVERED,
            subnet_id=subnet.id,
            created=None,
            updated=now,
        )

        mock_staticipaddress_repository.update.assert_called_once_with(
            None,
            (
                StaticIPAddressResourceBuilder()
                .with_ip("10.0.0.2")
                .with_lease_time(30)
                .with_alloc_type(IpAddressType.DISCOVERED)
                .with_subnet_id(subnet.id)
                .with_updated(now)
                .build()
            ),
        )

    async def test_get_discovered_ips_in_family_for_interfaces(
        self, db_connection: AsyncConnection
    ) -> None:
        now = datetime.utcnow()
        interface = Interface(
            id=1,
            name="eth0",
            type=InterfaceType.PHYSICAL,
            mac="00:11:22:33:44:55",
            created=now,
            updated=now,
        )

        mock_staticipaddress_repository = Mock(StaticIPAddressRepository)

        staticipaddress_service = StaticIPAddressService(
            db_connection, mock_staticipaddress_repository
        )

        await staticipaddress_service.get_discovered_ips_in_family_for_interfaces(
            [interface]
        )

        mock_staticipaddress_repository.get_discovered_ips_in_family_for_interfaces.assert_called_once_with(
            [interface], family=IpAddressFamily.IPV4
        )
