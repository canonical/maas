#  Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List, Type

from sqlalchemy import delete, desc, insert, select, Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.fields import normalise_macaddress
from maasservicelayer.context import Context
from maasservicelayer.db.mappers.interfaces import (
    DiscoveredInterfaceIP,
    DiscoveredInterfaceIPDomainDataMapper,
    InterfaceDetailsDomainDataMapper,
    InterfaceDomainDataMapper,
)
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceRelationshipTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
    VlanTable,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.utils.date import utcnow

UNKNOWN_INTERFACE_NAME = "eth0"


class InterfaceRepository(BaseRepository[Interface]):
    def __init__(self, context: Context):
        super().__init__(context)
        self.details_mapper = InterfaceDetailsDomainDataMapper(
            Interface, InterfaceTable
        )
        self.discovered_ip_mapper = DiscoveredInterfaceIPDomainDataMapper(
            DiscoveredInterfaceIP, StaticIPAddressTable
        )

    def get_repository_table(self) -> Table:
        return InterfaceTable

    def get_model_factory(self) -> Type[Interface]:
        return Interface

    def get_mapper(self) -> InterfaceDomainDataMapper:
        return InterfaceDomainDataMapper(Interface, InterfaceTable)

    async def list_for_node(
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
        total = (await self.execute_stmt(total_stmt)).scalar_one()

        stmt = (
            self.details_mapper.select_statement()
            .where(eq(NodeTable.c.id, node_id))
            .order_by(desc(InterfaceTable.c.id))
            .offset((page - 1) * size)
            .limit(size)
        )

        result = (await self.execute_stmt(stmt)).all()

        interfaces = [self.mapper.to_domain(row._mapping) for row in result]
        await self._find_discovered_ip_for_dhcp_links(interfaces, node_id)

        return ListResult[Interface](items=interfaces, total=total)

    async def get_interfaces_for_mac(self, mac: str) -> List[Interface]:
        stmt = self.details_mapper.select_statement().filter(
            InterfaceTable.c.mac_address == normalise_macaddress(mac)
        )

        result = (await self.execute_stmt(stmt)).all()
        return [self.mapper.to_domain(row._mapping) for row in result]

    async def get_parents(self, interface_id: int) -> list[Interface]:
        parent_ids = select(InterfaceRelationshipTable.c.parent_id).where(
            InterfaceRelationshipTable.c.child_id == interface_id
        )
        stmt = self.details_mapper.select_statement().where(
            InterfaceTable.c.id.in_(parent_ids)
        )
        rows = (await self.execute_stmt(stmt)).all()
        return [self.mapper.to_domain(row._mapping) for row in rows]

    async def get_interfaces_in_fabric(
        self, fabric_id: int
    ) -> List[Interface]:
        # Pair the retrieved interfaces with their respective VLAN and filter
        # out the ones corresponding to this fabric
        stmt = (
            self.details_mapper.select_statement()
            .join(
                VlanTable,
                eq(VlanTable.c.id, InterfaceTable.c.vlan_id),
                isouter=True,
            )
            .filter(VlanTable.c.fabric_id == fabric_id)
        )

        result = (await self.execute_stmt(stmt)).all()
        return [self.mapper.to_domain(row._mapping) for row in result]

    async def add_ip(self, interface: Interface, ip_id: int) -> None:
        stmt = (
            pg_insert(InterfaceIPAddressTable)
            .values(
                interface_id=interface.id,
                staticipaddress_id=ip_id,
            )
            .on_conflict_do_nothing()
        )

        await self.execute_stmt(stmt)

    async def remove_ip(self, interface: Interface, ip_id: int) -> None:
        stmt = delete(InterfaceIPAddressTable).where(
            InterfaceIPAddressTable.c.interface_id == interface.id,
            InterfaceIPAddressTable.c.staticipaddress_id == ip_id,
        )

        await self.execute_stmt(stmt)

    async def create_switch_interface(
        self, switch_id: int, mac: str, name: str = "mgmt0"
    ) -> int:
        now = utcnow()
        stmt = (
            insert(InterfaceTable)
            .returning(InterfaceTable.c.id)
            .values(
                name=name,
                mac_address=normalise_macaddress(mac),
                switch_id=switch_id,
                type=InterfaceType.PHYSICAL,
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
        return result[0]  # pyright: ignore [reportArgumentType]

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
                mac_address=normalise_macaddress(mac),
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

        get_instance = self.details_mapper.select_statement().where(
            eq(InterfaceTable.c.id, result[0])
        )
        created_instance = (await self.execute_stmt(get_instance)).one()
        return self.mapper.to_domain(created_instance._mapping)

    async def _find_discovered_ip_for_dhcp_links(
        self, interfaces: list[Interface], node_id: int
    ) -> None:
        if any(
            link.ip_type == IpAddressType.DHCP
            for iface in interfaces
            for link in iface.links
        ):
            discovered_ips = [
                self.discovered_ip_mapper.to_domain(discovered._mapping)
                for discovered in (
                    await self.execute_stmt(
                        self.discovered_ip_mapper.select_statement().where(
                            eq(NodeTable.c.id, node_id)
                        )
                    )
                ).all()
            ]
            for iface in interfaces:
                for link in iface.links:
                    if link.ip_type == IpAddressType.DHCP:
                        if ip := next(
                            filter(
                                lambda ip: ip.ip_subnet == link.ip_subnet,
                                discovered_ips,
                            ),
                            None,
                        ):
                            link.ip_address = ip.ip_address

    async def get_for_ip(self, ip_id: int) -> list[Interface] | None:
        stmt = (
            select(InterfaceTable)
            .select_from(StaticIPAddressTable)
            .join(
                InterfaceIPAddressTable,
                eq(
                    StaticIPAddressTable.c.id,
                    InterfaceIPAddressTable.c.staticipaddress_id,
                ),
            )
            .join(
                InterfaceTable,
                eq(
                    InterfaceIPAddressTable.c.interface_id, InterfaceTable.c.id
                ),
            )
            .filter(eq(StaticIPAddressTable.c.id, ip_id))
        )

        result = (await self.execute_stmt(stmt)).all()

        if not result:
            return None

        return [self.mapper.to_domain(row._mapping) for row in result]

    async def get_for_ips(
        self, ip_ids: list[int]
    ) -> dict[int, list[Interface]]:
        """Return interfaces linked to each of the given static IP ids."""
        interfaces_by_ip: dict[int, list[Interface]] = {}
        if not ip_ids:
            return interfaces_by_ip
        stmt = (
            select(
                InterfaceIPAddressTable.c.staticipaddress_id,
                InterfaceTable,
            )
            .select_from(StaticIPAddressTable)
            .join(
                InterfaceIPAddressTable,
                eq(
                    StaticIPAddressTable.c.id,
                    InterfaceIPAddressTable.c.staticipaddress_id,
                ),
            )
            .join(
                InterfaceTable,
                eq(
                    InterfaceIPAddressTable.c.interface_id, InterfaceTable.c.id
                ),
            )
            .filter(StaticIPAddressTable.c.id.in_(ip_ids))
        )
        result = (await self.execute_stmt(stmt)).all()
        for row in result:
            ip_id = row._mapping["staticipaddress_id"]
            interfaces_by_ip.setdefault(ip_id, []).append(
                self.mapper.to_domain(row._mapping)
            )
        return interfaces_by_ip

    async def unlink_interfaces_from_ips(
        self, interface_ids: list[int]
    ) -> None:
        """Remove the links between multiple interfaces and their IP addresses.

        Args:
            interface_ids: List of interface IDs to unlink
        """
        if not interface_ids:
            return

        stmt = delete(InterfaceIPAddressTable).where(
            InterfaceIPAddressTable.c.interface_id.in_(interface_ids)
        )
        await self.execute_stmt(stmt)
