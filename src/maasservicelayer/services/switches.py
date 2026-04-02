# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path

from maascommon.utils.images import get_bootresource_store_path
from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.interfaces import InterfaceClauseFactory
from maasservicelayer.db.repositories.switches import SwitchesRepository
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ConflictException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import CONFLICT_VIOLATION_TYPE
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.switches import Switch, SwitchWithTargetImage
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresources import BootResourceService
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
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
        boot_resources_service: BootResourceService,
        boot_resource_sets_service: BootResourceSetsService,
        boot_resource_files_service: BootResourceFilesService,
    ):
        super().__init__(context, switches_repository)
        self.staticipaddress_service = staticipaddress_service
        self.interfaces_service = interfaces_service
        self.boot_resources_service = boot_resources_service
        self.boot_resource_sets_service = boot_resource_sets_service
        self.boot_resource_files_service = boot_resource_files_service

    async def get_one_with_target_image(
        self, id: int
    ) -> SwitchWithTargetImage | None:
        return await self.repository.get_one_with_target_image(id)

    async def list_with_target_image(
        self, page: int, size: int
    ) -> ListResult[SwitchWithTargetImage]:
        return await self.repository.list_with_target_image(page, size)

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
        interface = await self.interfaces_service.get_one(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_mac_address(mac_address)
            )
        )

        if not interface or not interface.switch_id:
            return None

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

        if switch.target_image_id:
            return switch.target_image_id

        return None

    async def get_installer_file_for_switch(
        self, mac_address: str
    ) -> tuple[Path, str, int] | None:
        """Get the NOS installer file information for a switch.

        Args:
            mac_address: MAC address of the management interface

        Returns:
            Tuple of (file_path, filename, size) if installer assigned and file exists,
            None if no installer assigned

        Raises:
            NotFoundException: If switch not found or file not found on disk
        """
        boot_resource_id = await self.check_installer_for_switch(mac_address)
        if not boot_resource_id:
            return None

        boot_resource = await self.boot_resources_service.get_by_id(
            id=boot_resource_id
        )
        if not boot_resource:
            raise NotFoundException()

        resource_set = await self.boot_resource_sets_service.get_latest_complete_set_for_boot_resource(
            boot_resource.id
        )
        if not resource_set:
            raise NotFoundException()

        files = (
            await self.boot_resource_files_service.get_files_in_resource_set(
                resource_set.id
            )
        )
        if not files:
            raise NotFoundException()

        if len(files) != 1:
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=CONFLICT_VIOLATION_TYPE,
                        message=f"NOS installer images are expected to be self-extracting binaries with one (and only one) file, and it currently has {len(files)} files.",
                    )
                ]
            )
        boot_file = files[0]
        file_path = get_bootresource_store_path() / boot_file.filename_on_disk

        if not file_path.exists():
            raise NotFoundException()

        return (file_path, boot_file.filename, boot_file.size)

    async def pre_delete_hook(self, resource_to_be_deleted: Switch) -> None:
        """Clean up IP addresses on switch deletion

        This mimics the Django signal behavior from
        src/maasserver/models/signals/interfaces.py:delete_related_ip_addresses.

        Steps:
        1. Get all interfaces for this switch
        2. For each interface, unlink it from its IP addresses
        3. Delete IP addresses that no longer have any interface associations
        4. Let CASCADE handle the interface deletion

        Args:
            resource_to_be_deleted: The switch that is about to be deleted
        """
        interfaces = await self.interfaces_service.get_many(
            query=QuerySpec(
                where=InterfaceClauseFactory.with_switch_id(resource_to_be_deleted.id)
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
            )
            await self.staticipaddress_service.delete_ips_if_no_linked_interfaces(
                [i.id for i in ip_addresses]
            )
