# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Self

from maasapiserver.v3.api.public.models.responses.base import (
    BaseHal,
    BaseHref,
    HalResponse,
    PaginatedResponse,
)
from maasservicelayer.models.switches import Switch


class SwitchResponse(HalResponse[BaseHal]):
    """Response model for a single switch."""

    kind = "Switch"
    id: int
    hostname: Optional[str]
    vendor: Optional[str]
    model: Optional[str]
    platform: Optional[str]
    arch: Optional[str]
    serial_number: Optional[str]
    state: str
    target_image_id: Optional[int]

    @classmethod
    def from_model(cls, switch: Switch, self_base_hyperlink: str) -> Self:
        """Convert a Switch model to a response object."""
        return cls(
            id=switch.id,
            hostname=switch.hostname,
            vendor=switch.vendor,
            model=switch.model,
            platform=switch.platform,
            arch=switch.arch,
            serial_number=switch.serial_number,
            state=switch.state,
            target_image_id=switch.target_image_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{switch.id}"
                )
            ),
        )


class SwitchesListResponse(PaginatedResponse[SwitchResponse]):
    """Response model for a list of switches."""

    kind = "SwitchesList"
