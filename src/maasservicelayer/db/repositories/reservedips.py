# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from pydantic import IPvAnyAddress
from sqlalchemy import and_, cast, join, select, Table
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql.expression import exists
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ReservedIPTable, SubnetTable, VlanTable
from maasservicelayer.models.reservedips import ReservedIP


class ReservedIPsClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(ReservedIPTable.c.id, id))

    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(ReservedIPTable.c.subnet_id, subnet_id))

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> Clause:
        return Clause(
            condition=eq(SubnetTable.c.vlan_id, vlan_id),
            joins=[
                join(
                    ReservedIPTable,
                    SubnetTable,
                    eq(ReservedIPTable.c.subnet_id, SubnetTable.c.id),
                )
            ],
        )

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> Clause:
        return Clause(
            condition=eq(VlanTable.c.fabric_id, fabric_id),
            joins=[
                join(
                    ReservedIPTable,
                    SubnetTable,
                    eq(ReservedIPTable.c.subnet_id, SubnetTable.c.id),
                ),
                join(
                    VlanTable,
                    SubnetTable,
                    eq(VlanTable.c.id, SubnetTable.c.vlan_id),
                ),
            ],
        )


class ReservedIPsRepository(BaseRepository[ReservedIP]):
    def get_repository_table(self) -> Table:
        return ReservedIPTable

    def get_model_factory(self) -> Type[ReservedIP]:
        return ReservedIP

    async def exists_within_subnet_ip_range(
        self, subnet_id: int, start_ip: IPvAnyAddress, end_ip: IPvAnyAddress
    ) -> bool:
        stmt = select(1).where(
            and_(
                eq(ReservedIPTable.c.subnet_id, subnet_id),
                cast(ReservedIPTable.c.ip, INET).between(start_ip, end_ip),
            )
        )
        stmt = exists(stmt).select()
        return bool((await self.execute_stmt(stmt)).scalar())
