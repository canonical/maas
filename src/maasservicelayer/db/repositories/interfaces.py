#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.operators import eq, le

from maasserver.enum import IPADDRESS_TYPE
from maasservicelayer.db.tables import (  # TODO; VlanTable,
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface, Link


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


class InterfaceRepository:
    def __init__(self, connection: AsyncConnection):
        self.connection = connection

    async def list(
        self, node_id: int, token: str | None, size: int
    ) -> ListResult[Interface]:
        stmt = (
            self._select_all_statement()
            .where(eq(NodeTable.c.id, node_id))
            .order_by(desc(InterfaceTable.c.id))
            .limit(size + 1)
        )

        if token is not None:
            stmt = stmt.where(le(InterfaceTable.c.id, int(token)))

        result = (await self.connection.execute(stmt)).all()

        next_token = None
        if len(result) > size:  # There is another page
            next_token = result.pop().id

        interfaces = [build_interface_links(row._asdict()) for row in result]
        await self._find_discovered_ip_for_dhcp_links(interfaces, node_id)

        return ListResult[Interface](
            items=[Interface(**iface) for iface in interfaces],
            next_token=next_token,
        )

    async def _find_discovered_ip_for_dhcp_links(
        self, interfaces, node_id
    ) -> None:
        if any(
            link.ip_type == IPADDRESS_TYPE.DHCP
            for iface in interfaces
            for link in iface["links"]
        ):
            discovered_ips = [
                discovered._asdict()
                for discovered in (
                    await self.connection.execute(
                        self._discovered_ip_statement().where(
                            eq(NodeTable.c.id, node_id)
                        )
                    )
                ).all()
            ]
            for iface in interfaces:
                for link in iface["links"]:
                    if link.ip_type == IPADDRESS_TYPE.DHCP:
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
                    IPADDRESS_TYPE.DISCOVERED,
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
                StaticIPAddressTable.c.alloc_type != IPADDRESS_TYPE.DISCOVERED,
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
            .select_from(NodeTable)
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
