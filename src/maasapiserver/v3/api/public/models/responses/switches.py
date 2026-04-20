# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from pydantic import Field

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.switches import Switch, SwitchWithTargetImage


class SwitchResponse(HalResponse[BaseHal]):
    """Response model for a single switch.

    Represents a network switch device with its target image configuration.
    """

    kind: str = Field(default="Switch")
    id: int
    target_image_id: int | None = None
    target_image: str | None = None

    @classmethod
    def from_model(
        cls,
        switch: SwitchWithTargetImage,
        self_base_hyperlink: str,
    ) -> Self:
        """Convert a SwitchWithTargetImage model to a response object.

        Args:
            switch: The SwitchWithTargetImage model to convert.
            self_base_hyperlink: Base URL for HAL self link.

        Returns:
            SwitchResponse with all switch details including target image name.
        """
        return cls(
            id=switch.id,
            target_image_id=switch.target_image_id,
            target_image=switch.target_image,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{switch.id}"
                )
            ),
        )

    @classmethod
    def from_switch_model(
        cls,
        switch: Switch,
        target_image: str | None,
        self_base_hyperlink: str,
    ) -> Self:
        """Convert a Switch model to a response object.

        Args:
            switch: The Switch model to convert.
            target_image: The image name assigned to this switch.
            self_base_hyperlink: Base URL for HAL self link.

        Returns:
            SwitchResponse with all switch details including target image name.
        """
        return cls(
            id=switch.id,
            target_image_id=switch.target_image_id,
            target_image=target_image,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{switch.id}"
                )
            ),
        )


class SwitchesListResponse(PaginatedResponse[SwitchResponse]):
    """Response model for a paginated list of switches.

    Contains a collection of SwitchResponse items with pagination metadata.
    """

    kind: str = Field(default="SwitchesList")
