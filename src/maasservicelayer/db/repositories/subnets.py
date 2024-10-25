#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from netaddr import IPAddress
from pydantic import IPvAnyAddress
from sqlalchemy import desc, func, select, Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import SubnetTable, VlanTable
from maasservicelayer.models.subnets import Subnet


class SubnetsRepository(BaseRepository[Subnet]):

    def get_repository_table(self) -> Table:
        return SubnetTable

    def get_model_factory(self) -> Type[Subnet]:
        return Subnet

    async def find_best_subnet_for_ip(
        self, ip: IPvAnyAddress
    ) -> Subnet | None:
        ip_addr = IPAddress(str(ip))
        if ip_addr.is_ipv4_mapped():
            ip_addr = ip_addr.ipv4()

        stmt = (
            select(
                SubnetTable,
                func.masklen(SubnetTable.c.cidr).label("prefixlen"),
                VlanTable.c.dhcp_on,
            )
            .select_from(SubnetTable)
            .join(
                VlanTable,
                VlanTable.c.id == SubnetTable.c.vlan_id,
            )
            .order_by(
                desc(VlanTable.c.dhcp_on),
                desc("prefixlen"),
            )
        )

        result = (await self.connection.execute(stmt)).first()
        if not result:
            return None

        res = result._asdict()
        del res["prefixlen"]
        del res["dhcp_on"]
        return Subnet(**res)
