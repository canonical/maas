# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Callable
from ipaddress import ip_network, IPv4Address, IPv4Network

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.subnet import RdnsMode
from maasservicelayer.builders.subnets import SubnetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.filters.base import Filter
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.subnets import SubnetFilters
from maasservicelayer.models.subnets import Subnet
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestSubnetsRepository(RepositoryCommonTests[Subnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> SubnetsRepository:
        return SubnetsRepository(Context(connection=db_connection))

    @pytest.mark.parametrize(
        "cidrs, query_cidr, expected_indexes",
        [
            (
                [
                    "10.0.0.0/16",
                    "10.0.1.0/25",
                    "10.1.0.0/24",
                    "10.0.1.0/24",
                ],
                "10.0.1.0/24",
                {0, 1},
            ),
            (
                ["2001:db8::/32", "2001:db8:1::/64", "2001:db9::/64"],
                "2001:db8:1::/48",
                {0, 1},
            ),
        ],
    )
    async def test_cidr_overlap(
        self, repository_instance, fixture, cidrs, query_cidr, expected_indexes
    ):
        subnets = [
            await create_test_subnet_entry(fixture, cidr=cidr)
            for cidr in cidrs
        ]
        result = await repository_instance.get_many(
            QuerySpec(
                where=SubnetFilters.with_cidr_overlap(ip_network(query_cidr))
            )
        )
        assert {subnet.id for subnet in result} == {
            subnets[index]["id"] for index in expected_indexes
        }

    @pytest.mark.parametrize(
        "make_filter",
        [
            lambda subnet, vlan: SubnetFilters.with_fabric_id(
                vlan["fabric_id"]
            ),
            lambda subnet, vlan: SubnetFilters.with_vlan_id_in([vlan["id"]]),
            lambda subnet, vlan: SubnetFilters.with_not_rdns_mode(
                RdnsMode.DISABLED
            ),
        ],
    )
    async def test_filters(
        self,
        repository_instance: SubnetsRepository,
        fixture: Fixture,
        make_filter: Callable[[dict, dict], Filter],
    ):
        vlan = await create_test_vlan_entry(fixture)
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        await create_test_subnet_entry(fixture, rdns_mode=RdnsMode.DISABLED)
        result = await repository_instance.get_many(
            QuerySpec(where=make_filter(subnet, vlan))
        )
        assert [item.id for item in result] == [subnet["id"]]

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[Subnet]:
        created_subnets = [
            Subnet(
                **(
                    await create_test_subnet_entry(
                        fixture, name=str(i), description=str(i)
                    )
                )
            )
            for i in range(num_objects)
        ]
        return created_subnets

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Subnet:
        return Subnet(
            **(
                await create_test_subnet_entry(
                    fixture, name="name", description="description"
                )
            )
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[SubnetBuilder]:
        return SubnetBuilder

    @pytest.fixture
    async def instance_builder(self) -> SubnetBuilder:
        return SubnetBuilder(
            cidr=IPv4Network("10.10.10.1"),
            name="name",
            description="description",
            allow_dns=True,
            allow_proxy=True,
            rdns_mode=RdnsMode.DEFAULT,
            active_discovery=True,
            managed=True,
            disabled_boot_architectures=["ipxe"],
            gateway_ip=IPv4Address("10.0.0.1"),
            vlan_id=0,
        )

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_one_multiple_results(
        self, repository_instance, created_instance
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_by_id(self, repository_instance, created_instance):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_delete_many(self, repository_instance, created_instance):
        pass

    async def test_delete_checks_vlan_dhcp_on_dynamic_range(
        self, repository_instance: SubnetsRepository, fixture: Fixture
    ) -> None:
        vlan_with_dhcp_on = await create_test_vlan_entry(fixture, dhcp_on=True)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan_with_dhcp_on["id"]
        )
        await create_test_ip_range_entry(
            fixture, subnet=subnet, type="dynamic"
        )
        query = QuerySpec(where=SubnetFilters.with_id(subnet["id"]))
        with pytest.raises(ValidationException):
            await repository_instance.delete_one(query)

    async def test_delete_checks_vlan_dhcp_on_reserved_range(
        self, repository_instance: SubnetsRepository, fixture: Fixture
    ) -> None:
        vlan_with_dhcp_on = await create_test_vlan_entry(fixture, dhcp_on=True)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan_with_dhcp_on["id"]
        )
        await create_test_ip_range_entry(
            fixture, subnet=subnet, type="reserved"
        )
        query = QuerySpec(where=SubnetFilters.with_id(subnet["id"]))
        await repository_instance.delete_one(query)

    async def test_delete_checks_vlan_dhcp_off_dynamic_range(
        self, repository_instance: SubnetsRepository, fixture: Fixture
    ) -> None:
        vlan_with_dhcp_off = await create_test_vlan_entry(
            fixture, dhcp_on=False
        )
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan_with_dhcp_off["id"]
        )
        await create_test_ip_range_entry(
            fixture, subnet=subnet, type="dynamic"
        )
        query = QuerySpec(where=SubnetFilters.with_id(subnet["id"]))
        await repository_instance.delete_one(query)


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class TestSubnetsRepositoryMethods:
    async def test_find_best_subnet_for_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        await create_test_subnet_entry(fixture, cidr="10.0.0.0/25")
        subnet2 = await create_test_subnet_entry(fixture, cidr="10.0.1.0/24")

        ip = await create_test_staticipaddress_entry(fixture, ip="10.0.1.2")

        subnets = SubnetsRepository(Context(connection=db_connection))

        result = await subnets.find_best_subnet_for_ip(
            IPv4Address(ip[0]["ip"])
        )
        assert result is not None
        assert result.id == subnet2["id"]
