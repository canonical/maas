# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional, Union

from pydantic import IPvAnyAddress

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Switch(MaasTimestampedBaseModel):
    """Model representing a network switch.

    A switch is a network device that can be monitored and managed by MAAS.
    It tracks basic connectivity information including MAC address and IP address.
    """

    name: Optional[str]
    mac_address: str
    ip_address: Optional[Union[str, IPvAnyAddress]]
    model: Optional[str]
    manufacturer: Optional[str]
    description: Optional[str]
    vlan_id: Optional[int]
    subnet_id: Optional[int]
