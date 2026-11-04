# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.builders.ipranges import IPRangeBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ipranges import IPRangesRepository
from maasservicelayer.filters.ipranges import IPRangeFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


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
    async def instance_builder_model(self) -> type[IPRangeBuilder]:
        return IPRangeBuilder

    @pytest.fixture
    async def instance_builder(self) -> IPRangeBuilder:
        return IPRangeBuilder(
            type=IPRangeType.RESERVED,
            start_ip=IPv4Address("10.0.0.1"),
            end_ip=IPv4Address("10.0.0.2"),
            subnet_id=0,
        )

    # IP ranges constraints are not defined at DB level. We do a manual check
    # before creating the IP range in the pre_create_hook at the service level.
    @pytest.mark.skip
    async def test_create_duplicated(
        self,
        repository_instance: IPRangesRepository,
        instance_builder: IPRangeBuilder,
    ):
        pass

    @pytest.mark.skip
    async def test_create_many_duplicated(
        self,
        repository_instance: IPRangesRepository,
        instance_builder: IPRangeBuilder,
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

        result = await ipranges_repository.get_dynamic_range_for_ip(
            subnet.id, ip
        )

        assert result.id == dynamic_range["id"]

    @pytest.mark.parametrize("relation", ["vlan", "fabric", "both"])
    async def test_related_filters(
        self, repository_instance, fixture, relation
    ):
        vlan = await create_test_vlan_entry(fixture)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan["id"], cidr="10.0.0.0/24"
        )
        expected = await create_test_ip_range_entry(fixture, subnet=subnet)
        other_subnet = await create_test_subnet_entry(fixture)
        await create_test_ip_range_entry(fixture, subnet=other_subnet)
        vlan_filter = IPRangeFilters.with_vlan_id(vlan["id"])
        fabric_filter = IPRangeFilters.with_fabric_id(vlan["fabric_id"])
        filter = {
            "vlan": vlan_filter,
            "fabric": fabric_filter,
            "both": IPRangeFilters.and_filters(
                [
                    vlan_filter,
                    fabric_filter,
                    IPRangeFilters.with_subnet_ids([subnet["id"]]),
                    IPRangeFilters.with_start_ip(
                        IPv4Address(str(expected["start_ip"]))
                    ),
                    IPRangeFilters.with_end_ip(
                        IPv4Address(str(expected["end_ip"]))
                    ),
                ]
            ),
        }[relation]
        result = await repository_instance.get_many(QuerySpec(where=filter))
        assert [iprange.id for iprange in result] == [expected["id"]]
