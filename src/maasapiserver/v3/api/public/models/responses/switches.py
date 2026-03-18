# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.switches import Switch, SwitchWithTargetImage


class SwitchResponse(HalResponse[BaseHal]):
    """Response model for a single switch."""

    kind = "Switch"
    id: int
    target_image_id: int | None
    target_image: str | None

    @classmethod
    def from_model(
        cls,
        switch: SwitchWithTargetImage,
        self_base_hyperlink: str,
    ) -> Self:
        """Convert a Switch model to a response object.

        Args:
            switch: The switch model to convert
            self_base_hyperlink: Base URL for HAL links

        Returns:
            SwitchResponse with all switch details including target image name
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
            switch: The switch model to convert
            self_base_hyperlink: Base URL for HAL links

        Returns:
            SwitchResponse with all switch details including target image name
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
    """Response model for a list of switches."""

    kind = "SwitchesList"
