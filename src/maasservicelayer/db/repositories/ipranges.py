# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

import netaddr
from pydantic import IPvAnyAddress
from sqlalchemy import join, select, Table

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import IPRangeTable, SubnetTable, VlanTable
from maasservicelayer.models.ipranges import IPRange


class IPRangeClauseFactory(ClauseFactory):
    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.subnet_id, subnet_id))

    @classmethod
    def with_subnet_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=IPRangeTable.c.subnet_id.in_(ids))

    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.id, id))

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> Clause:
        return Clause(
            condition=eq(SubnetTable.c.vlan_id, vlan_id),
            joins=[
                join(
                    IPRangeTable,
                    SubnetTable,
                    eq(SubnetTable.c.id, IPRangeTable.c.subnet_id),
                )
            ],
        )

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> Clause:
        return Clause(
            condition=eq(VlanTable.c.fabric_id, fabric_id),
            joins=[
                join(
                    IPRangeTable,
                    SubnetTable,
                    eq(SubnetTable.c.id, IPRangeTable.c.subnet_id),
                ),
                join(
                    SubnetTable,
                    VlanTable,
                    eq(SubnetTable.c.vlan_id, VlanTable.c.id),
                ),
            ],
        )

    @classmethod
    def with_start_ip(cls, ip: IPvAnyAddress) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.start_ip, ip))

    @classmethod
    def with_end_ip(cls, ip: IPvAnyAddress) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.end_ip, ip))

    @classmethod
    def with_type(cls, type: IPRangeType) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.type, type))

    @classmethod
    def with_user_id(cls, user_id: int) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.user_id, user_id))


class IPRangesRepository(BaseRepository[IPRange]):
    def get_repository_table(self) -> Table:
        return IPRangeTable

    def get_model_factory(self) -> Type[IPRange]:
        return IPRange

    async def get_dynamic_range_for_ip(
        self, subnet_id: int, ip: IPvAnyAddress
    ) -> IPRange | None:
        stmt = (
            select(IPRangeTable)
            .select_from(IPRangeTable)
            .join(
                SubnetTable,
                SubnetTable.c.id == IPRangeTable.c.subnet_id,
            )
            .filter(SubnetTable.c.id == subnet_id)
        )

        result = (await self.execute_stmt(stmt)).all()

        ipranges = [IPRange(**row._asdict()) for row in result]

        netaddr_ip = netaddr.IPAddress(str(ip))

        for iprange in ipranges:
            if netaddr_ip in netaddr.IPRange(
                str(iprange.start_ip), str(iprange.end_ip)
            ):
                return iprange

        return None
