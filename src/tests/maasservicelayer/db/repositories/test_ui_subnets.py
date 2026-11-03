# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.ui_subnets import UISubnetsRepository
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.filters.ui_subnets import (
    UISubnetsFilters,
    UISubnetsOrdering,
)
from maasservicelayer.models.ui_subnets import UISubnet
from maasservicelayer.models.vlans import Vlan
from tests.fixtures.factories.fabric import create_test_fabric_entry
from tests.fixtures.factories.spaces import create_test_space_entry
from tests.fixtures.factories.subnet import create_test_ui_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import (
    ReadOnlyRepositoryCommonTests,
)


class TestUISubnetsRepository(ReadOnlyRepositoryCommonTests[UISubnet]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> UISubnetsRepository:
        return UISubnetsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[UISubnet]:
        space = await create_test_space_entry(fixture)
        vlan = Vlan(**await create_test_vlan_entry(fixture, space_id=space.id))
        created_ui_subnets = [
            await create_test_ui_subnet_entry(
                fixture, space=space, vlan=vlan, cidr=f"10.0.0.{i}"
            )
            for i in range(num_objects)
        ]
        return created_ui_subnets

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> UISubnet:
        return await create_test_ui_subnet_entry(fixture, cidr="10.0.0.1")

    @pytest.mark.parametrize(
        "filter_kind",
        [
            "cidrs",
            "vlan_ids",
            "fabric_names",
            "space_names",
            "fabric_like",
            "vlan_like",
            "space_like",
            "cidr_like",
            "subnet_ids",
        ],
    )
    async def test_domain_filters(
        self, repository_instance, fixture, filter_kind
    ):
        fabric = await create_test_fabric_entry(fixture, name="target-fabric")
        space = await create_test_space_entry(fixture, name="target-space")
        vlan = Vlan(
            **await create_test_vlan_entry(
                fixture,
                fabric_id=fabric.id,
                space_id=space.id,
                name="target-vlan",
            )
        )
        expected = await create_test_ui_subnet_entry(
            fixture, space=space, vlan=vlan, cidr="10.0.0.0/24"
        )
        other_space = await create_test_space_entry(
            fixture, name="other-space"
        )
        await create_test_ui_subnet_entry(
            fixture, space=other_space, cidr="192.168.0.0/24"
        )
        filters = {
            "cidrs": UISubnetsFilters.with_cidrs(["10.0.0.0/24"]),
            "vlan_ids": UISubnetsFilters.with_vlan_ids([vlan.id]),
            "fabric_names": UISubnetsFilters.with_fabric_names([fabric.name]),
            "space_names": UISubnetsFilters.with_space_names([space.name]),
            "fabric_like": UISubnetsFilters.with_fabric_name_like("target"),
            "vlan_like": UISubnetsFilters.with_vlan_name_like("target"),
            "space_like": UISubnetsFilters.with_space_name_like("target"),
            "cidr_like": UISubnetsFilters.with_cidr_like("10.0."),
            "subnet_ids": UISubnetsFilters.with_subnet_ids([expected.id]),
        }
        result = await repository_instance.get_many(
            QuerySpec(where=filters[filter_kind])
        )
        assert [subnet.id for subnet in result] == [expected.id]

    @pytest.mark.parametrize("descending", [False, True])
    async def test_cidr_ordering_is_numeric(
        self, repository_instance, fixture, descending
    ):
        space = await create_test_space_entry(fixture)
        vlan = Vlan(**await create_test_vlan_entry(fixture, space_id=space.id))
        subnets = [
            await create_test_ui_subnet_entry(
                fixture, space=space, vlan=vlan, cidr=cidr
            )
            for cidr in ["10.0.0.0/24", "2.0.0.0/24", "192.168.0.0/24"]
        ]
        order = UISubnetsOrdering.by_cidr()
        if descending:
            order = UISubnetsOrdering.desc(order)
        result = await repository_instance.get_many(
            QuerySpec(order_by=(order,))
        )
        expected = [subnets[1].id, subnets[0].id, subnets[2].id]
        if descending:
            expected.reverse()
        assert [subnet.id for subnet in result] == expected
