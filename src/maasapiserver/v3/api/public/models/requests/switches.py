# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field, IPvAnyAddress, validator

from maasapiserver.v3.api.public.models.requests.base import BaseModel
from maasservicelayer.builders.switches import (
    SwitchBuilder,
    SwitchInterfaceBuilder,
)


class SwitchRequest(BaseModel):
    """Request model for creating a switch."""

    mac_address: str
    hostname: Optional[str] = Field(
        default=None, description="User-defined hostname for DNS resolution."
    )
    image: Optional[int] = Field(
        default=None,
        description="Boot resource ID for the NOS to install on the switch.",
        alias="target_image_id",
    )
    ip_address: Optional[IPvAnyAddress] = Field(
        default=None,
        description="Static IP address to assign to the switch.",
    )

    def to_switch_builder(self, state: str = "registered") -> SwitchBuilder:
        return SwitchBuilder(
            hostname=self.hostname,
            state=state,
            target_image_id=self.image,
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
    image: Optional[int] = Field(
        default=None,
        description="Boot resource ID for the NOS to install on the switch.",
        alias="target_image_id",
    )
    ip_address: Optional[IPvAnyAddress] = Field(
        default=None,
        description="Static IP address to assign to the switch.",
    )

    def to_switch_builder(self) -> SwitchBuilder:
        return SwitchBuilder(
            hostname=self.hostname,
            target_image_id=self.image,
        )


class SwitchOperationRequest(BaseModel):
    """Request model for switch operations."""

    op: str = Field(description="Operation to perform (e.g., 'mark_fixed')")
    comment: Optional[str] = Field(
        default=None, description="Optional comment for the event log"
    )
