#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from netaddr import IPAddress, IPNetwork
from pydantic import IPvAnyAddress
from sqlalchemy import desc, func, select, Table

from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import SubnetTable, VlanTable
from maasservicelayer.models.subnets import Subnet


class SubnetResourceBuilder(ResourceBuilder):
    def with_cidr(self, cidr: IPNetwork) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.cidr.name, str(cidr))
        return self

    def with_name(self, name: str) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.name.name, name)
        return self

    def with_description(self, description: str) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.description.name, description)
        return self

    def with_allow_dns(self, allow_dns: bool) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.allow_dns.name, allow_dns)
        return self

    def with_allow_proxy(self, allow_proxy: bool) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.allow_proxy.name, allow_proxy)
        return self

    def with_rdns_mode(self, rdns_mode: int) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.rdns_mode.name, rdns_mode)
        return self

    def with_active_discovery(
        self, active_discovery: bool
    ) -> "SubnetResourceBuilder":
        self._request.set_value(
            SubnetTable.c.active_discovery.name, active_discovery
        )
        return self

    def with_managed(self, managed: bool) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.managed.name, managed)
        return self

    def with_disabled_boot_architectures(
        self, disabled_boot_architectures: list[str]
    ) -> "SubnetResourceBuilder":
        self._request.set_value(
            SubnetTable.c.disabled_boot_architectures.name,
            disabled_boot_architectures,
        )
        return self

    def with_gateway_ip(
        self, gateway_ip: IPvAnyAddress
    ) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.gateway_ip, gateway_ip)
        return self

    def with_vlan_id(self, vlan_id: int) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.vlan_id, vlan_id)
        return self


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
