# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maascommon.enums.switches import SwitchStatus
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Switch(MaasTimestampedBaseModel):
    """Model representing a network switch.

    A switch is a network device that can be monitored and managed by MAAS.
    """

    status: SwitchStatus
    target_image_id: Optional[int]


@generate_builder()
class SwitchInterface(MaasTimestampedBaseModel):
    """Model representing a switch interface.

    Each switch has one or more interfaces with network connectivity information.
    """

    mac_address: str
    switch_id: int
