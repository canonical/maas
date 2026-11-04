# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address, IPv6Address

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.reservedips import ReservedIPsRepository
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.reservedips import ReservedIPsFilters
from maasservicelayer.models.reservedips import ReservedIP
from tests.fixtures.factories.reserved_ips import create_test_reserved_ip_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestReservedIPsRepository(RepositoryCommonTests[ReservedIP]):
    async def test_related_filters_share_joins(
        self, fixture: Fixture, repository_instance: ReservedIPsRepository
    ) -> None:
        vlan = await create_test_vlan_entry(fixture)
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        expected = await create_test_reserved_ip_entry(fixture, subnet=subnet)
        unrelated = await create_test_subnet_entry(fixture)
        await create_test_reserved_ip_entry(fixture, subnet=unrelated)
        result = await repository_instance.get_many(
            QuerySpec(
                where=ReservedIPsFilters.and_filters(
                    [
                        ReservedIPsFilters.with_subnet_id(subnet["id"]),
                        ReservedIPsFilters.with_vlan_id(vlan["id"]),
                        ReservedIPsFilters.with_fabric_id(vlan["fabric_id"]),
                    ]
                )
            )
        )
        assert [item.id for item in result] == [expected["id"]]
        excluded = await repository_instance.get_many(
            QuerySpec(
                where=ReservedIPsFilters.and_filters(
                    [
                        ReservedIPsFilters.with_vlan_id(vlan["id"]),
                        ReservedIPsFilters.not_filter(
                            ReservedIPsFilters.with_fabric_id(
                                vlan["fabric_id"]
                            )
                        ),
                    ]
                )
            )
        )
        assert excluded == []

    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> ReservedIPsRepository:
        return ReservedIPsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[ReservedIP]:
        subnet = await create_test_subnet_entry(fixture)
        created_reserved_ips = [
            ReservedIP(
                **(
                    await create_test_reserved_ip_entry(
                        fixture,
                        subnet=subnet,
                        mac_address=f"01:02:03:04:05:{str(i).zfill(2)}",
                    )
                )
            )
            for i in range(num_objects)
        ]
        return created_reserved_ips

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> ReservedIP:
        subnet = await create_test_subnet_entry(fixture)
        return ReservedIP(
            **(await create_test_reserved_ip_entry(fixture, subnet=subnet))
        )

    @pytest.fixture
    async def instance_builder_model(self, *args, **kwargs):
        pass

    @pytest.fixture
    async def instance_builder(self, *args, **kwargs):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_many(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

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

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_by_id(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one(self, repository_instance, instance_builder):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_one_multiple_results(
        self, repository_instance, instance_builder
    ):
        pass

    @pytest.mark.skip(reason="Not implemented yet")
    async def test_update_many(self, repository_instance, instance_builder):
        pass

    @pytest.mark.parametrize(
        "ip, expected_result",
        [
            ("10.0.0.99", False),
            ("10.0.0.100", True),
            ("10.0.0.150", True),
            ("10.0.0.200", True),
            ("10.0.0.201", False),
        ],
    )
    async def test_exists_within_subnet_ipv4_range(
        self,
        repository_instance: ReservedIPsRepository,
        fixture: Fixture,
        ip: str,
        expected_result: bool,
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="10.0.0.0/24")
        await create_test_reserved_ip_entry(
            fixture, subnet=subnet, mac_address="01:02:03:04:05:06", ip=ip
        )
        exists = await repository_instance.exists_within_subnet_ip_range(
            subnet_id=subnet["id"],
            start_ip=IPv4Address("10.0.0.100"),
            end_ip=IPv4Address("10.0.0.200"),
        )
        assert exists == expected_result

    @pytest.mark.parametrize(
        "ip, expected_result",
        [
            ("fd00::1", False),
            ("fd00::100", True),
            ("fd00::150", True),
            ("fd00::200", True),
            ("fd00::201", False),
        ],
    )
    async def test_exists_within_subnet_ipv6_range(
        self,
        repository_instance: ReservedIPsRepository,
        fixture: Fixture,
        ip: str,
        expected_result: bool,
    ):
        subnet = await create_test_subnet_entry(fixture, cidr="fd00::/64")
        await create_test_reserved_ip_entry(
            fixture, subnet=subnet, mac_address="01:02:03:04:05:06", ip=ip
        )
        exists = await repository_instance.exists_within_subnet_ip_range(
            subnet_id=subnet["id"],
            start_ip=IPv6Address("fd00::100"),
            end_ip=IPv6Address("fd00::200"),
        )
        assert exists == expected_result
