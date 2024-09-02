# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import MaasTimestampedBaseModel


class Vlan(MaasTimestampedBaseModel):
    id: int
    vid: int
    name: Optional[str]
    description: str
    mtu: int
    dhcp_on: bool
    external_dhcp: Optional[str]
    primary_rack_id: Optional[str]
    secondary_rack_id: Optional[str]
    relay_vlan: Optional[int]
    fabric_id: int
    space_id: Optional[int]
