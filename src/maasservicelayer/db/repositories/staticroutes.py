# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import join, Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import StaticRouteTable, SubnetTable, VlanTable
from maasservicelayer.models.staticroutes import StaticRoute


class StaticRoutesClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(StaticRouteTable.c.id, id))

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> Clause:
        return Clause(
            condition=eq(SubnetTable.c.vlan_id, vlan_id),
            joins=[
                join(
                    StaticRouteTable,
                    SubnetTable,
                    eq(SubnetTable.c.id, StaticRouteTable.c.source_id),
                )
            ],
        )

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> Clause:
        return Clause(
            condition=eq(VlanTable.c.fabric_id, fabric_id),
            joins=[
                join(
                    StaticRouteTable,
                    SubnetTable,
                    eq(SubnetTable.c.id, StaticRouteTable.c.source_id),
                ),
                join(
                    SubnetTable,
                    VlanTable,
                    eq(SubnetTable.c.vlan_id, VlanTable.c.id),
                ),
            ],
        )

    @classmethod
    def with_source_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(StaticRouteTable.c.source_id, subnet_id))

    @classmethod
    def with_destination_id(cls, subnet_id: int) -> Clause:
        return Clause(
            condition=eq(StaticRouteTable.c.destination_id, subnet_id)
        )


class StaticRoutesRepository(BaseRepository[StaticRoute]):
    def get_repository_table(self) -> Table:
        return StaticRouteTable

    def get_model_factory(self) -> Type[StaticRoute]:
        return StaticRoute
