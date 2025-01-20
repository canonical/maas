# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder


class Vlan(MaasTimestampedBaseModel):
    id: int
    vid: int
    name: Optional[str] = None
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: Optional[str] = None
    primary_rack_id: Optional[int] = None
    secondary_rack_id: Optional[int] = None
    relay_vlan_id: Optional[int] = None
    fabric_id: int
    space_id: Optional[int] = None


VlanBuilder = make_builder(Vlan)
