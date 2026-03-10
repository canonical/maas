# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.switches import Switch
from maasservicelayer.services import ServiceCollectionV3


class SwitchResponse(HalResponse[BaseHal]):
    """Response model for a single switch."""

    kind = "Switch"
    id: int
    target_image_id: Optional[int]
    target_image: Optional[str]

    @classmethod
    async def from_model(
        cls,
        switch: Switch,
        self_base_hyperlink: str,
        services: ServiceCollectionV3,
    ) -> Self:
        """Convert a Switch model to a response object.

        Args:
            switch: The switch model to convert
            self_base_hyperlink: Base URL for HAL links
            services: Service collection for fetching boot resource name

        Returns:
            SwitchResponse with all switch details including target image name
        """
        target_image_name = None
        if switch.target_image_id:
            boot_resource = await services.boot_resources.get_by_id(
                switch.target_image_id
            )
            if boot_resource:
                target_image_name = boot_resource.name

        return cls(
            id=switch.id,
            target_image_id=switch.target_image_id,
            target_image=target_image_name,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{switch.id}"
                )
            ),
        )


class SwitchesListResponse(PaginatedResponse[SwitchResponse]):
    """Response model for a list of switches."""

    kind = "SwitchesList"
