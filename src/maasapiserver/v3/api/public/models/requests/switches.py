# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field, IPvAnyAddress, validator

from maasapiserver.v3.api.public.models.requests.base import BaseModel
from maasservicelayer.builders.switches import (
    SwitchBuilder,
    SwitchInterfaceBuilder,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.services import ServiceCollectionV3


class SwitchRequest(BaseModel):
    """Request model for creating a switch."""

    mac_address: str
    hostname: Optional[str] = Field(
        default=None, description="User-defined hostname for DNS resolution."
    )
    image: Optional[str] = Field(
        default=None,
        description="Boot resource name for the NOS to install on the switch. "
        "Supports full format (e.g., 'onie/mellanox-3.8.0') or short format "
        "for ONIE images (e.g., 'mellanox-3.8.0').",
        alias="target_image",
    )
    ip_address: Optional[IPvAnyAddress] = Field(
        default=None,
        description="Static IP address to assign to the switch.",
    )

    async def resolve_image_id(
        self, services: ServiceCollectionV3
    ) -> Optional[int]:
        """Resolve the image name to a boot resource ID.

        Supports both full format (onie/mellanox-3.8.0) and short format
        (mellanox-3.8.0). When using short format, validates that it's
        actually an ONIE image.

        Args:
            services: Service collection for accessing boot resources

        Returns:
            Boot resource ID if image name is provided and found, None otherwise

        Raises:
            ValidationException: If image name is provided but not found, or if
                short format name doesn't reference an ONIE image
        """
        if not self.image:
            return None

        # Try to find the boot resource with the provided name
        boot_resource = await services.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_name(self.image)
            )
        )

        # If not found and name doesn't contain '/', try prefixing with 'onie/'
        if not boot_resource and "/" not in self.image:
            prefixed_name = f"onie/{self.image}"
            boot_resource = await services.boot_resources.get_one(
                query=QuerySpec(
                    where=BootResourceClauseFactory.with_name(prefixed_name)
                )
            )
            
            # Validate that it's actually an ONIE image
            if boot_resource and not boot_resource.name.startswith("onie/"):
                raise ValidationException.build_for_field(
                    field="image",
                    message=f"Image '{self.image}' was found but is not an ONIE image. "
                    f"Found: '{boot_resource.name}'. When using short format (vendor-version), "
                    "the image must be an ONIE image.",
                )

        if not boot_resource:
            raise ValidationException.build_for_field(
                field="image",
                message=f"Boot resource '{self.image}' not found. "
                "Use full format 'onie/vendor-version' or short format 'vendor-version' for ONIE images. "
                "Use 'boot_resources' endpoint to list available images.",
            )

        return boot_resource.id

    async def to_switch_builder(
        self, services: ServiceCollectionV3, state: str = "registered"
    ) -> SwitchBuilder:
        target_image_id = await self.resolve_image_id(services)
        return SwitchBuilder(
            hostname=self.hostname,
            state=state,
            target_image_id=target_image_id,
        )

    def to_interface_builder(self, switch_id: int) -> SwitchInterfaceBuilder:
        return SwitchInterfaceBuilder(
            name="mgmt",  # Default management interface name
            mac_address=self.mac_address,
            switch_id=switch_id,
        )

    @validator("mac_address")
    def validate_mac_address(cls, v: str) -> str:
        """Validate MAC address format."""
        v = v.lower().strip()
        if not v:
            raise ValueError("MAC address cannot be empty")
        # Remove common separators and validate
        cleaned = v.replace(":", "").replace("-", "").replace(".", "")
        if len(cleaned) != 12:
            raise ValueError("MAC address must be 12 hex digits")
        try:
            int(cleaned, 16)
        except ValueError as e:
            raise ValueError(
                "MAC address must contain only hex digits"
            ) from e
        return v


class SwitchUpdateRequest(BaseModel):
    """Request model for updating a switch."""

    hostname: Optional[str] = Field(
        default=None, description="User-defined hostname for DNS resolution."
    )
    image: Optional[str] = Field(
        default=None,
        description="Boot resource name for the NOS to install on the switch. "
        "Supports full format (e.g., 'onie/mellanox-3.8.0') or short format "
        "for ONIE images (e.g., 'mellanox-3.8.0').",
        alias="target_image",
    )
    ip_address: Optional[IPvAnyAddress] = Field(
        default=None,
        description="Static IP address to assign to the switch.",
    )

    async def resolve_image_id(
        self, services: ServiceCollectionV3
    ) -> Optional[int]:
        """Resolve the image name to a boot resource ID.

        Supports both full format (onie/mellanox-3.8.0) and short format
        (mellanox-3.8.0). When using short format, validates that it's
        actually an ONIE image.

        Args:
            services: Service collection for accessing boot resources

        Returns:
            Boot resource ID if image name is provided and found, None otherwise

        Raises:
            ValidationException: If image name is provided but not found, or if
                short format name doesn't reference an ONIE image
        """
        if not self.image:
            return None

        # Try to find the boot resource with the provided name
        boot_resource = await services.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_name(self.image)
            )
        )

        # If not found and name doesn't contain '/', try prefixing with 'onie/'
        if not boot_resource and "/" not in self.image:
            prefixed_name = f"onie/{self.image}"
            boot_resource = await services.boot_resources.get_one(
                query=QuerySpec(
                    where=BootResourceClauseFactory.with_name(prefixed_name)
                )
            )
            
            # Validate that it's actually an ONIE image
            if boot_resource and not boot_resource.name.startswith("onie/"):
                raise ValidationException.build_for_field(
                    field="image",
                    message=f"Image '{self.image}' was found but is not an ONIE image. "
                    f"Found: '{boot_resource.name}'. When using short format (vendor-version), "
                    "the image must be an ONIE image.",
                )

        if not boot_resource:
            raise ValidationException.build_for_field(
                field="image",
                message=f"Boot resource '{self.image}' not found. "
                "Use full format 'onie/vendor-version' or short format 'vendor-version' for ONIE images. "
                "Use 'boot_resources' endpoint to list available images.",
            )

        return boot_resource.id

    async def to_switch_builder(
        self, services: ServiceCollectionV3
    ) -> SwitchBuilder:
        target_image_id = await self.resolve_image_id(services)
        return SwitchBuilder(
            hostname=self.hostname,
            target_image_id=target_image_id,
        )


class SwitchOperationRequest(BaseModel):
    """Request model for switch operations."""

    op: str = Field(description="Operation to perform (e.g., 'mark_fixed')")
    comment: Optional[str] = Field(
        default=None, description="Optional comment for the event log"
    )
