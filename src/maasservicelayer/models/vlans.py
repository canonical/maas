# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pydantic import IPvAnyAddress

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Vlan(MaasTimestampedBaseModel):
    id: int
    vid: int
    name: str | None = None
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: IPvAnyAddress | None = None
    primary_rack_id: int | None = None
    secondary_rack_id: int | None = None
    relay_vlan_id: int | None = None
    fabric_id: int
    space_id: int | None = None
    relayed_vlan_id: int | None = None
