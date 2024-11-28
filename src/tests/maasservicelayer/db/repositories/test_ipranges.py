from ipaddress import IPv4Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ipranges import (
    IPRangeResourceBuilder,
    IPRangesRepository,
)
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestIPRangesResourceBuilder:
    def test_builder(self) -> None:
        now = utcnow()
        resource = (
            IPRangeResourceBuilder()
            .with_type(IPRangeType.RESERVED)
            .with_start_ip(IPv4Address("10.0.0.1"))
            .with_end_ip(IPv4Address("10.0.0.1"))
            .with_subnet_id(0)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        assert resource.get_values() == {
            "type": IPRangeType.RESERVED,
            "start_ip": IPv4Address("10.0.0.1"),
            "end_ip": IPv4Address("10.0.0.1"),
            "subnet_id": 0,
            "created": now,
            "updated": now,
        }


@pytest.mark.asyncio
class TestIPRangesRepository(RepositoryCommonTests[IPRange]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> IPRangesRepository:
        return IPRangesRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[IPRange]:
        subnet = await create_test_subnet_entry(
            fixture, name="name", description="description"
        )
        created_ipranges = [
            IPRange(
                **(
                    await create_test_ip_range_entry(
                        fixture, subnet=subnet, offset=i
                    )
                )
            )
            for i in range(num_objects)
        ]
        return created_ipranges

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> IPRange:
        subnet = await create_test_subnet_entry(
            fixture, name="name", description="description"
        )
        return IPRange(
            **(await create_test_ip_range_entry(fixture, subnet=subnet))
        )

    @pytest.fixture
    async def instance_builder(self) -> IPRangeResourceBuilder:
        return (
            IPRangeResourceBuilder()
            .with_type(IPRangeType.RESERVED)
            .with_start_ip(IPv4Address("10.0.0.1"))
            .with_end_ip(IPv4Address("10.0.0.2"))
            .with_subnet_id(0)
        )

    # TODO: ip ranges contraints are not defined at DB level. We must check them
    # manually before creating the ip range.
    @pytest.mark.skip
    async def test_create_duplicated(
        self,
        repository_instance: IPRangesRepository,
        instance_builder: IPRangeResourceBuilder,
    ):
        pass

    async def test_get_dyanmic_range_for_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ):
        subnet_data = await create_test_subnet_entry(
            fixture, cidr="10.0.0.0/24"
        )
        subnet = Subnet(**subnet_data)
        ip = IPv4Address("10.0.0.2")
        dynamic_range = await create_test_ip_range_entry(
            fixture,
            subnet=subnet_data,
            offset=1,
            size=5,
            type=IPRangeType.DYNAMIC,
        )

        ipranges_repository = IPRangesRepository(
            Context(connection=db_connection)
        )

        result = await ipranges_repository.get_dynamic_range_for_ip(subnet, ip)

        assert result.id == dynamic_range["id"]
