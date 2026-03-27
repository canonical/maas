# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone

from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.switches import Switch
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService


class SwitchesService(BaseService[Switch, SwitchesRepository, SwitchBuilder]):
    """Service for managing network switches.

    This service provides business logic for creating, reading, updating,
    and deleting network switches in MAAS.
    """

    def __init__(
        self,
        context: Context,
        switches_repository: SwitchesRepository,
        staticipaddress_service: StaticIPAddressService,
        interfaces_service: InterfacesService,
    ):
        super().__init__(context, switches_repository)
        self.staticipaddress_service = staticipaddress_service
        self.interfaces_service = interfaces_service

    async def create_new_switch_and_interface(
        self,
        builder: SwitchBuilder,
        mac_address: str,
    ) -> Switch:
        """Create a new switch and interface.

        Args:
            builder: SwitchBuilder with the switch details
            mac_address: MAC address for the management interface
        Returns:
            The created Switch
        """
        switch = await self.create(builder)
        await self.interfaces_service.create_switch_interface(
            switch_id=switch.id, mac=mac_address
        )
        return switch

    async def create_switch_and_link_interface(
        self,
        builder: SwitchBuilder,
        interface_id: int,
    ) -> Switch:
        """Create a new switch and link an existing interface to it.

        This method is used when an UNKNOWN interface already exists
        (e.g., created by DHCP lease commit) and needs to be claimed
        by the new switch.

        Args:
            builder: SwitchBuilder with the switch details
            interface_id: ID of the existing interface to link
        Returns:
            The created Switch
        """
        switch = await self.create(builder)
        await self.interfaces_service.link_interface_to_switch(
            interface_id=interface_id, switch_id=switch.id
        )
        return switch

    async def get_switch_by_mac_address(
        self, mac_address: str
    ) -> Switch | None:
        """Get a switch by its management interface MAC address.

        Args:
            mac_address: MAC address of the management interface

        Returns:
            The Switch if found, None otherwise
        """
        # Find the interface with this MAC address
        interface = await self.interfaces_service.get_one(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_mac_address(mac_address)
            )
        )

        if not interface or not interface.switch_id:
            return None

        # Get the switch
        return await self.get_by_id(id=interface.switch_id)

    async def check_installer_for_switch(self, mac_address: str) -> int | None:
        """Check if a switch has an assigned NOS installer, and
        return its image ID if it exists.

        Args:
            mac_address: MAC address of the management interface

        Returns:
            The boot resource ID of the assigned NOS installer, or None

        Raises:
            NotFoundException: If the switch is not found
        """
        switch = await self.get_switch_by_mac_address(mac_address)
        if not switch:
            raise NotFoundException()

        # Update heartbeat timestamp
        await self.update_by_id(
            id=switch.id,
            builder=SwitchBuilder(updated=datetime.now(timezone.utc)),
        )

        # Return the target image ID if assigned
        if switch.target_image_id:
            return switch.target_image_id

        return None

    async def post_delete_hook(self, resource: Switch) -> None:
        """Clean up IP addresses on switch deletion

        This mimics the Django signal behavior from
        src/maasserver/models/signals/interfaces.py:delete_related_ip_addresses.

        Steps:
        1. Get all interfaces for this switch
        2. For each interface, unlink it from its IP addresses
        3. Delete IP addresses that no longer have any interface associations
        4. Let CASCADE handle the interface deletion

        Args:
            resource: The switch that was deleted
        """
        interfaces = await self.interfaces_service.get_many(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_switch_id(resource.id)
            )
        )
        if not interfaces:
            return

        interface_ids = [iface.id for iface in interfaces]
        for interface_id in interface_ids:
            ip_addresses = await self.staticipaddress_service.get_ip_addresses_for_interface(
                interface_id
            )
            await self.interfaces_service.unlink_interface_from_ips(
                interface_id=interface_id,
                staticipaddress_ids=[i.id for i in ip_addresses],
            )
            for ip in ip_addresses:
                await self.staticipaddress_service.delete_ip_if_no_linked_interfaces(
                    ip.id
                )
