# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Optional

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Switch(MaasTimestampedBaseModel):
    """Model representing a network switch.

    A switch is a network device that can be monitored and managed by MAAS.
    """

    target_image_id: Optional[int]
