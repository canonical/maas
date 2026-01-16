# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Switch(MaasTimestampedBaseModel):
    """Model representing a network switch.

    A switch is a network device discovered via ONIE DHCP that can be
    monitored and managed by MAAS.
    """

    hostname: Optional[str]
    vendor: Optional[str]
    model: Optional[str]
    platform: Optional[str]
    arch: Optional[str]
    serial_number: Optional[str]
    state: str  # e.g., 'new', 'registered', 'ready', 'deploying', 'deployed', 'broken'
    target_image_id: Optional[int]


@generate_builder()
class SwitchInterface(MaasTimestampedBaseModel):
    """Model representing a switch interface.

    Each switch has one or more interfaces with network connectivity information.
    """

    name: str
    mac_address: str
    switch_id: int
    ip_address_id: Optional[int]
