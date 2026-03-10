# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import BaseModel, Field

from maasservicelayer.builders.switches import SwitchBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.services import ServiceCollectionV3


async def resolve_image_id(
    image: str | None, services: ServiceCollectionV3
) -> Optional[int]:
    """Resolve the image name to a boot resource ID.

    Supports both full format (onie/mellanox-3.8.0) and short format
    (mellanox-3.8.0). When using short format, validates that it's
    actually an ONIE image.

    Args:
        image: Image name
        services: Service collection for accessing boot resources

    Returns:
        Boot resource ID if image name is provided and found, None otherwise

    Raises:
        ValidationException: If image name is provided but not found, or if
            short format name doesn't reference an ONIE image
    """
    if not image:
        return None

    # Try to find the boot resource with the provided name
    boot_resource = await services.boot_resources.get_one(
        query=QuerySpec(where=BootResourceClauseFactory.with_name(image))
    )

    if (
        boot_resource
        and "/" in image
        and not boot_resource.name.startswith("onie/")
    ):
        raise ValidationException.build_for_field(
            field="image",
            message=f"Image '{image}' was found but is not an ONIE image. "
            f"Found: '{boot_resource.name}'.",
        )

    # If not found and name doesn't contain '/', try prefixing with 'onie/'
    if not boot_resource and "/" not in image:
        prefixed_name = f"onie/{image}"
        boot_resource = await services.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_name(prefixed_name)
            )
        )

    if not boot_resource:
        raise ValidationException.build_for_field(
            field="image",
            message=f"Boot resource '{image}' not found. "
            "Use full format 'onie/vendor-version' or short format 'vendor-version' for ONIE images. "
            "Use 'boot_resources' endpoint to list available images.",
        )

    return boot_resource.id


class SwitchRequest(BaseModel):
    """Request model for creating a switch."""

    mac_address: MacAddress
    image: Optional[str] = Field(
        default=None,
        description="Boot resource name for the NOS to install on the switch. "
        "Supports full format (e.g., 'onie/mellanox-3.8.0') or short format "
        "for ONIE images (e.g., 'mellanox-3.8.0').",
    )

    async def to_switch_builder(
        self, services: ServiceCollectionV3
    ) -> SwitchBuilder:
        target_image_id = await resolve_image_id(self.image, services)
        return SwitchBuilder(
            target_image_id=target_image_id,
        )


class SwitchUpdateRequest(BaseModel):
    """Request model for updating a switch."""

    image: Optional[str] = Field(
        default=None,
        description="Boot resource name for the NOS to install on the switch. "
        "Supports full format (e.g., 'onie/mellanox-3.8.0') or short format "
        "for ONIE images (e.g., 'mellanox-3.8.0').",
    )

    async def to_switch_builder(
        self, services: ServiceCollectionV3
    ) -> SwitchBuilder:
        target_image_id = await resolve_image_id(self.image, services)
        return SwitchBuilder(
            target_image_id=target_image_id,
        )
