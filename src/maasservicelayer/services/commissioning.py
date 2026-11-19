#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import structlog

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.models.nodes import Node
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

        # Collect all IP addresses that are not DISCOVERED and need to be cleared.
        ips_to_clear = {
            ip.id: ip
            for ip in await self.staticipaddress_service.get_for_interfaces(
                [interface.id for interface in interfaces]
            )
            if ip.alloc_type != IpAddressType.DISCOVERED
        }
        for ip in ips_to_clear.values():
            logger.info(
                f"{node.hostname}: IP address automatically unlinked: {ip.ip}"
            )
            await self.staticipaddress_service.delete_by_id(ip.id)
