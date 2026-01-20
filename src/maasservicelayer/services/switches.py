# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from typing import Optional

from structlog import get_logger

from maasservicelayer.builders.switches import (
    SwitchBuilder,
    SwitchInterfaceBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.switches import (
    SwitchesRepository,
    SwitchInterfaceClauseFactory,
    SwitchInterfacesRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.switches import Switch, SwitchInterface
from maasservicelayer.services.base import BaseService

logger = get_logger()


class SwitchesService(BaseService[Switch, SwitchesRepository, SwitchBuilder]):
    """Service for managing network switches.

    This service provides business logic for creating, reading, updating,
    and deleting network switches in MAAS. Switches represent network
    devices that can be monitored and managed.
    """

    def __init__(
        self,
        context: Context,
        switches_repository: SwitchesRepository,
        switchinterfaces_repository: SwitchInterfacesRepository,
    ):
        super().__init__(context, switches_repository)
        self.switchinterfaces_repository = switchinterfaces_repository

    async def get_switch_by_mac_address(
        self, mac_address: str
    ) -> Optional[Switch]:
        """Get a switch by its management interface MAC address.

        Args:
            mac_address: MAC address of the management interface

        Returns:
            The Switch if found, None otherwise
        """
        # Find the interface with this MAC address
        interface = await self.switchinterfaces_repository.get_one(
            query=QuerySpec(
                where=SwitchInterfaceClauseFactory.with_mac_address(
                    mac_address
                )
            )
        )

        if not interface:
            return None

        # Get the switch
        return await self.get_by_id(id=interface.switch_id)

    async def check_installer_for_switch(
        self, mac_address: str
    ) -> Optional[int]:
        """Check if a switch has an assigned NOS installer.

        This method handles the logic for GET /onie/nos-installer:
        - Returns the assigned target_image_id if present
        - Updates heartbeat timestamp
        - Returns None if no installer is assigned

        Args:
            mac_address: MAC address of the management interface

        Returns:
            The boot resource ID of the assigned NOS installer, or None

        Raises:
            NotFoundException: If the switch is not found
        """
        switch = await self.get_switch_by_mac_address(mac_address)
        logger.info(
            "Checking installer for switch",
            mac_address=mac_address,
            switch=switch,
        )
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


class SwitchInterfacesService(
    BaseService[
        SwitchInterface, SwitchInterfacesRepository, SwitchInterfaceBuilder
    ]
):
    """Service for managing switch interfaces."""

    def __init__(
        self,
        context: Context,
        switchinterfaces_repository: SwitchInterfacesRepository,
    ):
        super().__init__(context, switchinterfaces_repository)
