#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any, List

from sqlalchemy import desc, insert, Select, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    VlanTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface, Link
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.utils.date import utcnow

UNKNOWN_INTERFACE_NAME = "eth0"


def build_interface_links(
    interface: dict[str, list[dict[str, Any]]], reverse=True
) -> dict[str, list[Link]]:
    if links := interface.pop("links"):
        one_link_per_id = {
            link["id"]: Link(**link) for link in links if any(link.values())
        }
        sorted_links = sorted(
            one_link_per_id.values(), key=lambda link: link.id, reverse=reverse
        )
        interface["links"] = sorted_links
    return interface


class InterfaceRepository(Repository):
    async def list(
        self, node_id: int, page: int, size: int
    ) -> ListResult[Interface]:
        total_stmt = (
            select(count())
            .select_from(InterfaceTable)
            .join(
                NodeConfigTable,
                eq(NodeConfigTable.c.id, InterfaceTable.c.node_config_id),
                isouter=True,
            )
            .join(
                NodeTable,
                eq(NodeTable.c.current_config_id, NodeConfigTable.c.id),
                isouter=True,
            )
            .where(eq(NodeTable.c.id, node_id))
        )
        total = (await self.execute_stmt(total_stmt)).scalar()

        stmt = (
            self._select_all_statement()
            .where(eq(NodeTable.c.id, node_id))
            .order_by(desc(InterfaceTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )

        result = (await self.execute_stmt(stmt)).all()

        interfaces = [build_interface_links(row._asdict()) for row in result]
        await self._find_discovered_ip_for_dhcp_links(interfaces, node_id)

        return ListResult[Interface](
            items=[Interface(**iface) for iface in interfaces],
            total=total,
        )

    async def get_interfaces_for_mac(self, mac: str) -> List[Interface]:
        stmt = self._select_all_statement().filter(
            InterfaceTable.c.mac_address == mac
        )

        result = (await self.execute_stmt(stmt)).all()
        return [
            Interface(**data)
            for data in [
                build_interface_links(row._asdict()) for row in result
            ]
        ]

    async def get_interfaces_in_fabric(
        self, fabric_id: int
    ) -> List[Interface]:
        # Pair the retrieved interfaces with their respective VLAN and filter
        # out the ones corresponding to this fabric
        # TODO: If _select_all_statement ever joins with VlanTable, remove the
        #       join below.
        stmt = (
            self._select_all_statement()
            .join(
                VlanTable,
                eq(VlanTable.c.id, InterfaceTable.c.vlan_id),
                isouter=True,
            )
            .filter(VlanTable.c.fabric_id == fabric_id)
        )

        result = (await self.execute_stmt(stmt)).all()
        return [
            Interface(**data)
            for data in [
                build_interface_links(row._asdict()) for row in result
            ]
        ]

    async def link_ip(self, interface: Interface, ip: StaticIPAddress) -> None:
        stmt = (
            pg_insert(InterfaceIPAddressTable)
            .values(
                interface_id=interface.id,
                staticipaddress_id=ip.id,
            )
            .on_conflict_do_nothing()
        )

        await self.execute_stmt(stmt)

    async def create_unknwown_interface(
        self, mac: str, vlan_id: int
    ) -> Interface:
        """TODO: we are rethinking the way we manage interfaces and storage. The current domain model is still WIP and requires
        some joins, so here we have to first insert and fetch again the instance even if it's suboptimal.
        """
        now = utcnow()
        stmt = (
            insert(InterfaceTable)
            .returning(InterfaceTable.c.id)
            .values(
                name=UNKNOWN_INTERFACE_NAME,
                mac_address=mac,
                vlan_id=vlan_id,
                type=InterfaceType.UNKNOWN,
                params={},
                enabled=True,
                mdns_discovery_state=False,
                neighbour_discovery_state=False,
                acquired=False,
                link_connected=True,
                interface_speed=0,
                link_speed=0,
                sriov_max_vf=0,
                created=now,
                updated=now,
            )
        )
        result = (await self.execute_stmt(stmt)).one()

        get_instance = self._select_all_statement().where(
            eq(InterfaceTable.c.id, result[0])
        )
        created_instance = (await self.execute_stmt(get_instance)).one()
        return Interface(**build_interface_links(created_instance._asdict()))

    async def _find_discovered_ip_for_dhcp_links(
        self, interfaces, node_id
    ) -> None:
        if any(
            link.ip_type == IpAddressType.DHCP
            for iface in interfaces
            for link in iface["links"]
        ):
            discovered_ips = [
                discovered._asdict()
                for discovered in (
                    await self.execute_stmt(
                        self._discovered_ip_statement().where(
                            eq(NodeTable.c.id, node_id)
                        )
                    )
                ).all()
            ]
            for iface in interfaces:
                for link in iface["links"]:
                    if link.ip_type == IpAddressType.DHCP:
                        if ip := next(
                            filter(
                                lambda ip: ip["ip_subnet"] == link.ip_subnet,
                                discovered_ips,
                            ),
                            None,
                        ):
                            link.ip_address = ip["ip_address"]

    def _discovered_ip_statement(self) -> Select[Any]:
        return (
            select(
                StaticIPAddressTable.c.subnet_id.label("ip_subnet"),
                StaticIPAddressTable.c.ip.label("ip_address"),
            )
            .select_from(NodeTable)
            .where(
                eq(
                    StaticIPAddressTable.c.alloc_type,
                    IpAddressType.DISCOVERED,
                )
            )
            .join(
                NodeConfigTable,
                eq(NodeTable.c.current_config_id, NodeConfigTable.c.id),
                isouter=True,
            )
            .join(
                InterfaceTable,
                eq(NodeConfigTable.c.id, InterfaceTable.c.node_config_id),
                isouter=True,
            )
            .join(
                InterfaceIPAddressTable,
                eq(
                    InterfaceTable.c.id, InterfaceIPAddressTable.c.interface_id
                ),
                isouter=True,
            )
            .join(
                StaticIPAddressTable,
                eq(
                    InterfaceIPAddressTable.c.staticipaddress_id,
                    StaticIPAddressTable.c.id,
                ),
                isouter=True,
            )
            .distinct(StaticIPAddressTable.c.subnet_id)
        )

    def _select_all_statement(self) -> Select[Any]:
        ip_subquery = (
            select(
                InterfaceIPAddressTable.c.interface_id.label("interface_id"),
                StaticIPAddressTable.c.subnet_id.label("ip_subnet"),
                StaticIPAddressTable.c.id.label("ip_id"),
                StaticIPAddressTable.c.alloc_type.label("ip_type"),
                StaticIPAddressTable.c.ip.label("ip_address"),
            )
            .where(
                eq(
                    InterfaceIPAddressTable.c.staticipaddress_id,
                    StaticIPAddressTable.c.id,
                ),
                StaticIPAddressTable.c.alloc_type != IpAddressType.DISCOVERED,
            )
            .order_by(desc(StaticIPAddressTable.c.id))
            .alias("ip_subquery")
        )

        return (
            select(
                NodeTable.c.id.label("node_id"),
                InterfaceTable.c.id,
                InterfaceTable.c.created,
                InterfaceTable.c.updated,
                InterfaceTable.c.name,
                InterfaceTable.c.type,
                InterfaceTable.c.mac_address,
                # TODO
                # VlanTable.c.mtu.label("effective_mtu"),
                InterfaceTable.c.link_connected,
                InterfaceTable.c.interface_speed,
                InterfaceTable.c.enabled,
                InterfaceTable.c.link_speed,
                InterfaceTable.c.sriov_max_vf,
                func.array_agg(
                    func.json_build_object(
                        "id",
                        ip_subquery.c.ip_id,
                        "ip_type",
                        ip_subquery.c.ip_type,
                        "ip_address",
                        ip_subquery.c.ip_address,
                        "ip_subnet",
                        ip_subquery.c.ip_subnet,
                    )
                ).label("links"),
            )
            .select_from(InterfaceTable)
            .join(
                NodeConfigTable,
                eq(NodeConfigTable.c.id, InterfaceTable.c.node_config_id),
                isouter=True,
            )
            .join(
                NodeTable,
                eq(NodeTable.c.current_config_id, NodeConfigTable.c.id),
                isouter=True,
            )
            # TODO
            # .join(
            #     VlanTable,
            #     eq(VlanTable.c.id, InterfaceTable.c.vlan_id),
            #     isouter=True,
            # )
            .join(
                InterfaceIPAddressTable,
                eq(
                    InterfaceTable.c.id, InterfaceIPAddressTable.c.interface_id
                ),
                isouter=True,
            )
            .join(
                ip_subquery,
                eq(ip_subquery.c.interface_id, InterfaceTable.c.id),
                isouter=True,
            )
            .group_by(
                NodeTable.c.id,
                InterfaceTable.c.id,
                # VlanTable.c.mtu,
            )
        )
