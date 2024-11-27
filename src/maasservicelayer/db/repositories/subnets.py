#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from netaddr import IPAddress
from pydantic import IPvAnyAddress
from sqlalchemy import desc, func, join, select, Table

from maascommon.bootmethods import find_boot_method_by_arch_or_octet
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import SubnetTable, VlanTable
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.utils.validators import IPv4v6Network


class SubnetClauseFactory(ClauseFactory):
    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SubnetTable.c.id, id))

    @classmethod
    def with_vlan_id(cls, vlan_id: int) -> Clause:
        return Clause(condition=eq(SubnetTable.c.vlan_id, vlan_id))

    @classmethod
    def with_fabric_id(cls, fabric_id: int) -> Clause:
        return Clause(
            condition=eq(VlanTable.c.fabric_id, fabric_id),
            joins=[
                join(
                    SubnetTable,
                    VlanTable,
                    eq(SubnetTable.c.vlan_id, VlanTable.c.id),
                )
            ],
        )


class SubnetResourceBuilder(ResourceBuilder):
    def with_cidr(self, cidr: IPv4v6Network) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.cidr.name, cidr)
        return self

    def with_name(self, name: str) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.name.name, name)
        return self

    def with_description(
        self, description: str | None
    ) -> "SubnetResourceBuilder":
        # inherited from the django model where it's empty by default.
        if description is None:
            description = ""
        self._request.set_value(SubnetTable.c.description.name, description)
        return self

    def with_allow_dns(self, allow_dns: bool) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.allow_dns.name, allow_dns)
        return self

    def with_allow_proxy(self, allow_proxy: bool) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.allow_proxy.name, allow_proxy)
        return self

    def with_rdns_mode(self, rdns_mode: RdnsMode) -> "SubnetResourceBuilder":
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
        disabled_boot_method_names = []
        for disabled_arch in disabled_boot_architectures:
            boot_method = find_boot_method_by_arch_or_octet(
                disabled_arch, disabled_arch.replace("0x", "00:")
            )
            if boot_method is None or (
                not boot_method.arch_octet and not boot_method.path_prefix_http
            ):
                raise ValidationException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message=f"Unkown boot architecture {disabled_arch}",
                        )
                    ]
                )
            disabled_boot_method_names.append(boot_method.name)
        self._request.set_value(
            SubnetTable.c.disabled_boot_architectures.name,
            disabled_boot_method_names,
        )
        return self

    def with_gateway_ip(
        self, gateway_ip: IPvAnyAddress | None
    ) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.gateway_ip.name, gateway_ip)
        return self

    def with_dns_servers(
        self, dns_servers: list[IPvAnyAddress]
    ) -> "SubnetResourceBuilder":
        values = [str(server) for server in dns_servers]
        self._request.set_value(SubnetTable.c.dns_servers.name, values)
        return self

    def with_vlan_id(self, vlan_id: int) -> "SubnetResourceBuilder":
        self._request.set_value(SubnetTable.c.vlan_id.name, vlan_id)
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
            .where(SubnetTable.c.cidr.op(">>")(ip_addr))
        )

        result = (await self.connection.execute(stmt)).first()
        if not result:
            return None

        res = result._asdict()
        del res["prefixlen"]
        del res["dhcp_on"]
        return Subnet(**res)
