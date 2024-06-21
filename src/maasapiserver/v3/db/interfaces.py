from typing import Any

from sqlalchemy import desc, select, Select
from sqlalchemy.sql.expression import func
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import (  # TODO; VlanTable,
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
)
from maasapiserver.v3.api.models.requests.interfaces import InterfaceRequest
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.interfaces import Interface, Link
from maasserver.enum import IPADDRESS_TYPE


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


class InterfaceRepository(BaseRepository[Interface, InterfaceRequest]):
    async def create(self, request: InterfaceRequest) -> Interface:
        raise Exception("Not implemented yet.")

    async def find_by_id(self, id: int) -> Interface | None:
        raise Exception("Not implemented yet.")

    async def list(
        self, node_id: int, pagination_params: PaginationParams
    ) -> ListResult[Interface]:
        total_stmt = (
            select(count(InterfaceTable.c.id))
            .select_from(NodeTable)
            .where(eq(NodeTable.c.id, node_id))
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
        )
        total = (await self.connection.execute(total_stmt)).scalar()

        stmt = (
            self._select_all_statement()
            .where(eq(NodeTable.c.id, node_id))
            .order_by(desc(InterfaceTable.c.id))
            .offset((pagination_params.page - 1) * pagination_params.size)
            .limit(pagination_params.size)
        )

        interfaces = [
            build_interface_links(row._asdict())
            for row in (await self.connection.execute(stmt)).all()
        ]
        await self._find_discovered_ip_for_dhcp_links(interfaces, node_id)

        return ListResult[Interface](
            items=[Interface(**iface) for iface in interfaces],
            total=total,
        )

    async def list_with_token(
        self, token: str | None, size: int
    ) -> ListResult[Interface]:
        raise Exception("Not implemented yet.")

    async def update(self, resource: Interface) -> Interface:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        raise Exception("Not implemented yet.")

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
