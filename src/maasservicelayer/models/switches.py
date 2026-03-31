# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Switch(MaasTimestampedBaseModel):
    """Model representing a network switch.

    A switch is a network device provisioned by MAAS.
    """

    target_image_id: int | None


class SwitchWithTargetImage(Switch):
    """Model representing a network switch, with it's target image name."""

    target_image: str | None

    @classmethod
    def from_switch(cls, switch: Switch, target_image: str | None) -> Self:
        return cls(
            id=switch.id,
            target_image_id=switch.target_image_id,
            created=switch.created,
            updated=switch.updated,
            target_image=target_image,
        )
