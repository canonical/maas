# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field, IPvAnyAddress, validator

from maasapiserver.v3.api.public.models.requests.base import NamedBaseModel
from maasservicelayer.builders.switches import SwitchBuilder


class SwitchRequest(NamedBaseModel):
    """Request model for creating or updating a switch."""

    mac_address: str
    ip_address: Optional[IPvAnyAddress]
    model: Optional[str]
    manufacturer: Optional[str]
    description: Optional[str] = Field(
        default="", description="Description of the switch."
    )
    vlan_id: Optional[int]
    subnet_id: Optional[int]

    def to_builder(self) -> SwitchBuilder:
        return SwitchBuilder(
            name=self.name,
            description=self.description,
            mac_address=self.mac_address,
            ip_address=self.ip_address,
        )

    @validator("mac_address")
    def validate_mac_address(cls, v: str) -> str:
        """Validate MAC address format."""
        # Basic validation - could be more robust
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
            raise ValueError("MAC address must contain only hex digits") from e
        return v
