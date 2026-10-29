# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

import netaddr
from pydantic import IPvAnyAddress
from sqlalchemy import select, Table

from maasservicelayer.db.mappers.ipranges import IPRangeDomainDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import IPRangeTable, SubnetTable
from maasservicelayer.models.ipranges import IPRange


class IPRangesRepository(BaseRepository[IPRange]):
    def get_repository_table(self) -> Table:
        return IPRangeTable

    def get_model_factory(self) -> Type[IPRange]:
        return IPRange

    def get_mapper(self) -> IPRangeDomainDataMapper:
        return IPRangeDomainDataMapper(IPRange, IPRangeTable)

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
