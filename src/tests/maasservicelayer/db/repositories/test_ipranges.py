from ipaddress import IPv4Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ipranges import (
    IPRangeResourceBuilder,
    IPRangesRepository,
)
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


class TestIPRangesResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            IPRangeResourceBuilder()
            .with_type("type")
            .with_start_ip("10.0.0.1")
            .with_end_ip("10.0.0.1")
            .with_subnet_id(0)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        assert resource.get_values() == {
            "type": "type",
            "start_ip": "10.0.0.1",
            "end_ip": "10.0.0.1",
            "subnet_id": 0,
            "created": now,
            "updated": now,
        }


@pytest.mark.asyncio
class TestIPRangesRepository:
    async def test_get_dyanmic_range_for_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet_data = await create_test_subnet_entry(
            fixture, cidr="10.0.0.0/24"
        )
        subnet = Subnet(**subnet_data)
        ip = IPv4Address("10.0.0.2")
        dynamic_range = await create_test_ip_range_entry(
            fixture, subnet=subnet_data, offset=1, size=5, type="dynamic"
        )

        ipranges_repository = IPRangesRepository(
            Context(connection=db_connection)
        )

        result = await ipranges_repository.get_dynamic_range_for_ip(subnet, ip)

        assert result.id == dynamic_range["id"]
