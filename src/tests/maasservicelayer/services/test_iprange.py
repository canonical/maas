from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.ipranges import IPRangesService


@pytest.mark.asyncio
class TestIPRangesService:
    async def test_get_dynamic_range_for_ip(
        self, db_connection: AsyncConnection
    ) -> None:
        subnet = Subnet(
            id=1,
            cidr="10.0.0.0/24",
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            rdns_mode=1,
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=[],
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.1",
            subnet_id=subnet.id,
            lease_time=600,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
            alloc_type=IpAddressType.DISCOVERED,
        )

        mock_ipranges_repository = Mock(IPRangesRepository)

        ipranges_service = IPRangesService(
            db_connection, ipranges_repository=mock_ipranges_repository
        )

        await ipranges_service.get_dynamic_range_for_ip(subnet, sip)

        mock_ipranges_repository.get_dynamic_range_for_ip.assert_called_once_with(
            subnet, "10.0.0.1"
        )
