# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

import netaddr
from pydantic import IPvAnyAddress
from sqlalchemy import select, Table

from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import IPRangeTable, SubnetTable
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet


class IPRangeClauseFactory(ClauseFactory):
    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(condition=eq(IPRangeTable.c.subnet_id, subnet_id))

    @classmethod
    def with_subnet_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=IPRangeTable.c.subnet_id.in_(ids))


class IPRangeResourceBuilder(ResourceBuilder):
    def with_type(self, type: IPRangeType) -> "IPRangeResourceBuilder":
        self._request.set_value(IPRangeTable.c.type.name, type)
        return self

    def with_start_ip(self, ip: IPvAnyAddress) -> "IPRangeResourceBuilder":
        self._request.set_value(IPRangeTable.c.start_ip.name, ip)
        return self

    def with_end_ip(self, ip: IPvAnyAddress) -> "IPRangeResourceBuilder":
        self._request.set_value(IPRangeTable.c.end_ip.name, ip)
        return self

    def with_subnet_id(self, id: int) -> "IPRangeResourceBuilder":
        self._request.set_value(IPRangeTable.c.subnet_id.name, id)
        return self


class IPRangesRepository(BaseRepository[IPRange]):
    def get_repository_table(self) -> Table:
        return IPRangeTable

    def get_model_factory(self) -> Type[IPRange]:
        return IPRange

    async def get_dynamic_range_for_ip(
        self, subnet: Subnet, ip: IPvAnyAddress
    ) -> IPRange | None:
        stmt = (
            select(IPRangeTable)
            .select_from(IPRangeTable)
            .join(
                SubnetTable,
                SubnetTable.c.id == IPRangeTable.c.subnet_id,
            )
            .filter(SubnetTable.c.id == subnet.id)
        )

        result = (await self.connection.execute(stmt)).all()

        ipranges = [IPRange(**row._asdict()) for row in result]

        netaddr_ip = netaddr.IPAddress(str(ip))

        for iprange in ipranges:
            if netaddr_ip in netaddr.IPRange(
                str(iprange.start_ip), str(iprange.end_ip)
            ):
                return iprange

        return None
