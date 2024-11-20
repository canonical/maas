# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from pydantic import Field

from maasapiserver.v3.api.public.models.requests.base import (
    OptionalNamedBaseModel,
)
from maasservicelayer.db.repositories.vlans import VlanResourceBuilder
from maasservicelayer.utils.date import utcnow


class VlanCreateRequest(OptionalNamedBaseModel):
    description: Optional[str] = Field(
        description="The description of the VLAN.", default=None
    )
    vid: int = Field(
        description="The VLAN ID of the VLAN. Valid values are within the range [0, 4094]."
    )
    # Linux doesn't allow lower than 552 for the MTU.
    mtu: Optional[int] = Field(
        description="The MTU to use on the VLAN. Valid values are within the range [552, 65535].",
        default=None,
    )
    space_id: Optional[int] = Field(
        description="The space this VLAN should be placed in. If not specified, the VLAN will be "
        "placed in the 'undefined' space."
    )

    def to_builder(self) -> VlanResourceBuilder:
        now = utcnow()
        return (
            VlanResourceBuilder()
            .with_name(self.name)
            .with_description(self.description)
            .with_vid(self.vid)
            .with_mtu(self.mtu)
            .with_dhcp_on(False)
            .with_space_id(self.space_id)
            .with_created(now)
            .with_updated(now)
        )
