#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services._base import Service


class InterfacesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        interface_repository: InterfaceRepository | None = None,
    ):
        super().__init__(connection)
        self.interface_repository = (
            interface_repository
            if interface_repository
            else InterfaceRepository(connection)
        )

    async def list(
        self, node_id: int, token: str | None, size: int
    ) -> ListResult[Interface]:
        return await self.interface_repository.list(
            node_id=node_id, token=token, size=size
        )

    async def get_interfaces_for_mac(self, mac: str) -> List[Interface]:
        return await self.interface_repository.get_interfaces_for_mac(mac)

    async def bulk_link_ip(
        self, sip: StaticIPAddress, interfaces: List[Interface]
    ) -> None:
        for interface in interfaces:
            await self.interface_repository.add_ip(interface, sip)

    async def add_ip(self, interface: Interface, sip: StaticIPAddress) -> None:
        await self.interface_repository.add_ip(interface, sip)
