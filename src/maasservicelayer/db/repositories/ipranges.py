import netaddr
from sqlalchemy import select

from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResource,
)
from maasservicelayer.db.tables import IPRangeTable, SubnetTable
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.subnets import Subnet


class IPRangesRepository(BaseRepository):
    async def delete(self, id: int) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def find_by_id(self, id: int) -> IPRange | None:
        raise NotImplementedError("Not implemented yet.")

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[IPRange]:
        raise NotImplementedError("Not implemented yet.")

    async def create(self, resource: CreateOrUpdateResource) -> IPRange:
        raise NotImplementedError("Not implemented yet.")

    async def update(
        self, id: int, resource: CreateOrUpdateResource
    ) -> IPRange:
        raise NotImplementedError("Not implemented yet.")

    async def get_dynamic_range_for_ip(
        self, subnet: Subnet, ip: str
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

        netaddr_ip = netaddr.IPAddress(ip)

        for iprange in ipranges:
            if netaddr_ip in netaddr.IPRange(
                str(iprange.start_ip), str(iprange.end_ip)
            ):
                return iprange

        return None
