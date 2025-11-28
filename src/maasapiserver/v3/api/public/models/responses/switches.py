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
    name: str
    mac_address: str
    ip_address: Optional[str]
    model: Optional[str]
    manufacturer: Optional[str]
    description: str
    vlan_id: Optional[int]
    subnet_id: Optional[int]

    @classmethod
    def from_model(cls, switch: Switch, self_base_hyperlink: str) -> Self:
        """Convert a Switch model to a response object."""
        return cls(
            id=switch.id,
            name=switch.name,
            mac_address=switch.mac_address,
            ip_address=str(switch.ip_address) if switch.ip_address else None,
            model=switch.model,
            manufacturer=switch.manufacturer,
            description=switch.description,
            vlan_id=switch.vlan_id,
            subnet_id=switch.subnet_id,
            hal_links=BaseHal(  # pyright: ignore [reportCallIssue]
                self=BaseHref(
                    href=f"{self_base_hyperlink.rstrip('/')}/{switch.id}"
                )
            ),
        )


class SwitchesListResponse(PaginatedResponse[SwitchResponse]):
    """Response model for a list of switches."""

    kind = "SwitchesList"
