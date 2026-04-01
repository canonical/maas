# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.enums.ztp import ZTPDeliveryMechanism
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Switch(MaasTimestampedBaseModel):
    """Model representing a network switch.

    A switch is a network device provisioned by MAAS.
    """

    target_image_id: Optional[int]
    ztp_enabled: bool = False
    ztp_script_key: Optional[str] = None
    ztp_delivery_mechanism: Optional[ZTPDeliveryMechanism] = None
    mgmt_mac_address: Optional[str] = None
