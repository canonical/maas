# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.ipranges import (
    IPRangeClauseFactory,
    IPRangesRepository,
)
from maasservicelayer.db.tables import IPRangeTable
from maasservicelayer.models.ipranges import IPRange, IPRangeBuilder
from maasservicelayer.models.subnets import Subnet
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestIPRangeClauseFactory:
    def test_with_id(self) -> None:
        clause = IPRangeClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_iprange.id = 1")

    def test_with_subnet_id(self) -> None:
        clause = IPRangeClauseFactory.with_subnet_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_iprange.subnet_id = 1")

    def test_with_vlan_id(self):
        clause = IPRangeClauseFactory.with_vlan_id(vlan_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_subnet.vlan_id = 1")
        assert str(
            clause.joins[0].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_iprange JOIN maasserver_subnet ON maasserver_subnet.id = maasserver_iprange.subnet_id"
        )

    def test_with_fabric_id(self):
        clause = IPRangeClauseFactory.with_fabric_id(fabric_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_vlan.fabric_id = 1")
        assert str(
            clause.joins[0].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_iprange JOIN maasserver_subnet ON maasserver_subnet.id = maasserver_iprange.subnet_id"
        )

    def test_and_clause(self) -> None:
        clause = IPRangeClauseFactory.and_clauses(
            [
                IPRangeClauseFactory.with_subnet_id(subnet_id=1),
                IPRangeClauseFactory.with_vlan_id(vlan_id=1),
                IPRangeClauseFactory.with_fabric_id(fabric_id=1),
            ]
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_iprange.subnet_id = 1 AND maasserver_subnet.vlan_id = 1 AND maasserver_vlan.fabric_id = 1"
        )
        compiled_joins = [
            str(_join.compile(compile_kwargs={"literal_binds": True}))
            for _join in clause.joins
        ]

        # Joins at this stage are expected to be duplicated. They will be merged together when the query statement is enriched
        # by the QuerySpec.
        assert len(compiled_joins) == 3
        assert (
            "maasserver_iprange JOIN maasserver_subnet ON maasserver_subnet.id = maasserver_iprange.subnet_id"
            in compiled_joins
        )
        assert (
            "maasserver_subnet JOIN maasserver_vlan ON maasserver_subnet.vlan_id = maasserver_vlan.id"
            in compiled_joins
        )

    def test_and_clause_enrich_statement(self) -> None:
        clause = IPRangeClauseFactory.and_clauses(
            [
                IPRangeClauseFactory.with_subnet_id(subnet_id=1),
                IPRangeClauseFactory.with_vlan_id(vlan_id=1),
                IPRangeClauseFactory.with_fabric_id(fabric_id=1),
            ]
        )
        stmt = select(IPRangeTable.c.id).select_from(IPRangeTable)
        query = QuerySpec(clause)
        stmt = query.enrich_stmt(stmt)
        expected_query = (
            "SELECT maasserver_iprange.id \n"
            "FROM maasserver_iprange JOIN maasserver_subnet ON maasserver_subnet.id = maasserver_iprange.subnet_id JOIN maasserver_vlan ON maasserver_subnet.vlan_id = maasserver_vlan.id \n"
            "WHERE maasserver_iprange.subnet_id = 1 AND maasserver_subnet.vlan_id = 1 AND maasserver_vlan.fabric_id = 1"
        )
        assert (
            str(stmt.compile(compile_kwargs={"literal_binds": True}))
            == expected_query
        )


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
