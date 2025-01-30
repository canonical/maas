# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Zone(MaasTimestampedBaseModel):
    name: str
    description: str


class ZoneWithSummary(Zone):
    devices_count: int
    machines_count: int
    controllers_count: int
