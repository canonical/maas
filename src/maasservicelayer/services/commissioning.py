#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import structlog

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.base import Service
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService

logger = structlog.getLogger()


class CommissioningService(Service):
    def __init__(
        self,
        context: Context,
        interfaces_service: InterfacesService,
        nodes_service: NodesService,
        staticipaddress_service: StaticIPAddressService,
    ):
        super().__init__(context)
        self.interfaces_service = interfaces_service
        self.nodes_service = nodes_service
        self.staticipaddress_service = staticipaddress_service

    async def clear_networking_configuration(self, node: Node) -> None:
        """Remove every link except DISCOVERED ones from the node's interfaces,
        so that commissioning can build a fresh networking configuration."""
        await self.nodes_service.update_by_id(
            node.id,
            NodeBuilder(gateway_link_ipv4_id=None, gateway_link_ipv6_id=None),
        )
        if node.current_config_id is None:
            return

        interfaces = await self.interfaces_service.get_many(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_node_config_id(
                    node.current_config_id
                )
            )
        )
        if not interfaces:
            return

        # An address linked to more than one interface is returned once per
        # link.
        ips_to_clear = {
            ip.id: ip
            for ip in await self.staticipaddress_service.get_for_interfaces(
                [interface.id for interface in interfaces]
            )
            if ip.alloc_type != IpAddressType.DISCOVERED
        }
        bmc_ip_ids = (
            await self.staticipaddress_service.get_ids_referenced_by_bmcs(
                list(ips_to_clear)
            )
        )
        for ip in ips_to_clear.values():
            logger.info(
                f"{node.hostname}: IP address automatically unlinked: {ip.ip}"
            )
            if ip.id in bmc_ip_ids:
                await self._release_ip_shared_with_bmc(ip)
            else:
                await self.staticipaddress_service.delete_by_id(ip.id)

    async def _release_ip_shared_with_bmc(self, ip: StaticIPAddress) -> None:
        # The BMC foreign key has no ON DELETE action in the database, so
        # deleting the row would fail at commit. Django deletes it and the BMC
        # then recreates an unlinked STICKY address for the same IP; keeping
        # the row reaches that same end state.
        await self.staticipaddress_service.unlink_from_interfaces(ip.id)
        await self.staticipaddress_service.update_by_id(
            ip.id,
            StaticIPAddressBuilder(
                alloc_type=IpAddressType.STICKY,
                user_id=None,
                temp_expires_on=None,
            ),
        )
