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
    SwitchClauseFactory,
    SwitchesRepository,
    SwitchInterfaceClauseFactory,
    SwitchInterfacesRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    NotFoundException,
)
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

    async def enlist_or_update_switch(
        self,
        serial_number: str,
        mac_address: str,
        vendor: Optional[str] = None,
        model: Optional[str] = None,
        arch: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> Switch:
        """Enlist a new switch or update an existing one from ONIE headers.

        During automatic enlistment, creates a new switch in 'new' state.
        During manual enlistment, updates an existing 'registered' switch to 'ready' state.

        Args:
            serial_number: Switch serial number
            mac_address: MAC address of the management interface
            vendor: Switch vendor (e.g., 'Dell', 'Arista')
            model: Switch model
            arch: Architecture
            platform: Platform identifier

        Returns:
            The created or updated Switch

        Raises:
            BadRequestException: If vendor mismatch occurs on a registered switch with assigned NOS
        """
        # Try to find existing switch by serial number
        existing_switch = await self.repository.get_one(
            query=QuerySpec(
                where=SwitchClauseFactory.with_serial_number(serial_number)
            )
        )

        if existing_switch:
            # Check if this is a registered switch being enlisted
            if existing_switch.state == "registered":
                # Check for vendor mismatch with assigned NOS
                if existing_switch.target_image_id and existing_switch.vendor:
                    if (
                        vendor
                        and vendor.lower() != existing_switch.vendor.lower()
                    ):
                        # Vendor mismatch - mark as broken
                        await self.update_by_id(
                            id=existing_switch.id,
                            builder=SwitchBuilder(
                                state="broken",
                                updated=datetime.now(timezone.utc),
                            ),
                        )
                        raise BadRequestException(
                            f"Vendor mismatch: expected {existing_switch.vendor}, got {vendor}"
                        )

                # Update to ready state
                return await self.update_by_id(
                    id=existing_switch.id,
                    builder=SwitchBuilder(
                        state="ready",
                        vendor=vendor,
                        model=model,
                        arch=arch,
                        platform=platform,
                        updated=datetime.now(timezone.utc),
                    ),
                )
            else:
                # Just update the timestamp for heartbeat tracking
                return await self.update_by_id(
                    id=existing_switch.id,
                    builder=SwitchBuilder(updated=datetime.now(timezone.utc)),
                )
        else:
            # Create new switch in 'new' state (automatic enlistment)
            switch = await self.create(
                builder=SwitchBuilder(
                    serial_number=serial_number,
                    vendor=vendor,
                    model=model,
                    arch=arch,
                    platform=platform,
                    state="new",
                )
            )

            # Create the management interface
            await self.switchinterfaces_repository.create(
                SwitchInterfaceBuilder(
                    name="mgmt",
                    mac_address=mac_address,
                    switch_id=switch.id,
                )
            )

            return switch

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
        - For switches in 'ready' state, returns the assigned target_image_id if present
        - For switches in 'new' state, updates heartbeat and returns None
        - For other states, returns None

        Args:
            mac_address: MAC address of the management interface

        Returns:
            The boot resource ID of the assigned NOS installer, or None

        Raises:
            NotFoundException: If the switch is not found
            BadRequestException: If vendor mismatch with assigned NOS
        """
        switch = await self.get_switch_by_mac_address(mac_address)
        logger.info("Checking installer for switch", mac_address=mac_address, switch=switch)
        if not switch:
            raise NotFoundException()

        # Update heartbeat timestamp
        await self.update_by_id(
            id=switch.id,
            builder=SwitchBuilder(updated=datetime.now(timezone.utc)),
        )

        # if switch.state == "ready":
            # Check if NOS is assigned
        if switch.target_image_id:
            return switch.target_image_id
            # return None
        elif switch.state == "new":
            # Switch remains in 'new', keep idling
            return None
        else:
            # Other states (deploying, deployed, broken) - no installer
            return None

    async def mark_installation_complete(self, mac_address: str) -> Switch:
        """Mark a switch installation as complete and transition to 'deployed' state.

        This method handles the POST /onie/nos-installer endpoint.

        Args:
            mac_address: MAC address of the management interface

        Returns:
            The updated Switch in 'deployed' state

        Raises:
            NotFoundException: If the switch is not found
        """
        switch = await self.get_switch_by_mac_address(mac_address)
        if not switch:
            raise NotFoundException(
                f"Switch with MAC address {mac_address} not found"
            )

        # Transition to deployed state
        return await self.update_by_id(
            id=switch.id,
            builder=SwitchBuilder(
                state="deployed",
                updated=datetime.now(timezone.utc),
            ),
        )


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
