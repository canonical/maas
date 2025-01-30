# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)
from maasservicelayer.models.fields import IPv4v6Network


@generate_builder()
class StaticRoute(MaasTimestampedBaseModel):
    name: str
    cidr: IPv4v6Network
    metric: int
    destination_id: int
    source_id: int
