# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
    ReservedIPsRepository,
)
from maasservicelayer.db.tables import ReservedIPTable
from maasservicelayer.models.reservedips import ReservedIP
from tests.fixtures.factories.reserved_ips import create_test_reserved_ip_entry
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestReservedIPsClauseFactory:
    def test_with_id(self) -> None:
        clause = ReservedIPsClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_reservedip.id = 1")

    def test_with_subnet_id(self) -> None:
        clause = ReservedIPsClauseFactory.with_subnet_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_reservedip.subnet_id = 1")

    def test_with_vlan_id(self):
        clause = ReservedIPsClauseFactory.with_vlan_id(vlan_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_subnet.vlan_id = 1")
        assert str(
            clause.joins[0].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_reservedip JOIN maasserver_subnet ON maasserver_reservedip.subnet_id = maasserver_subnet.id"
        )

    def test_with_fabric_id(self):
        clause = ReservedIPsClauseFactory.with_fabric_id(fabric_id=1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_vlan.fabric_id = 1")
        assert str(
            clause.joins[0].compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_reservedip JOIN maasserver_subnet ON maasserver_reservedip.subnet_id = maasserver_subnet.id"
        )

    def test_and_clause(self) -> None:
        clause = ReservedIPsClauseFactory.and_clauses(
            [
                ReservedIPsClauseFactory.with_subnet_id(subnet_id=1),
                ReservedIPsClauseFactory.with_vlan_id(vlan_id=1),
                ReservedIPsClauseFactory.with_fabric_id(fabric_id=1),
            ]
        )
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == (
            "maasserver_reservedip.subnet_id = 1 AND maasserver_subnet.vlan_id = 1 AND maasserver_vlan.fabric_id = 1"
        )
        compiled_joins = [
            str(_join.compile(compile_kwargs={"literal_binds": True}))
            for _join in clause.joins
        ]

        # Joins at this stage are expected to be duplicated. They will be merged together when the query statement is enriched
        # by the QuerySpec.
        assert len(compiled_joins) == 3
        assert (
            "maasserver_reservedip JOIN maasserver_subnet ON maasserver_reservedip.subnet_id = maasserver_subnet.id"
            in compiled_joins
        )
        assert (
            "maasserver_vlan JOIN maasserver_subnet ON maasserver_vlan.id = maasserver_subnet.vlan_id"
            in compiled_joins
        )

    def test_and_clause_enrich_statement(self) -> None:
        clause = ReservedIPsClauseFactory.and_clauses(
            [
                ReservedIPsClauseFactory.with_subnet_id(subnet_id=1),
                ReservedIPsClauseFactory.with_vlan_id(vlan_id=1),
                ReservedIPsClauseFactory.with_fabric_id(fabric_id=1),
            ]
        )
        stmt = select(ReservedIPTable.c.id).select_from(ReservedIPTable)
        query = QuerySpec(clause)
        stmt = query.enrich_stmt(stmt)
        expected_query = (
            "SELECT maasserver_reservedip.id \n"
            "FROM maasserver_reservedip JOIN maasserver_subnet ON maasserver_reservedip.subnet_id = maasserver_subnet.id JOIN maasserver_vlan ON maasserver_vlan.id = maasserver_subnet.vlan_id \n"
            "WHERE maasserver_reservedip.subnet_id = 1 AND maasserver_subnet.vlan_id = 1 AND maasserver_vlan.fabric_id = 1"
        )
        assert (
            str(stmt.compile(compile_kwargs={"literal_binds": True}))
            == expected_query
        )


class TestReservedIPsRepository(RepositoryCommonTests[ReservedIP]):
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
    async def test_update(self, repository_instance, instance_builder):
        pass
