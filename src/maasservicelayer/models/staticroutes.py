# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.models.base import MaasTimestampedBaseModel, make_builder
from maasservicelayer.models.fields import IPv4v6Network


class StaticRoute(MaasTimestampedBaseModel):
    name: str
    cidr: IPv4v6Network
    metric: int
    destination_id: int
    source_id: int


StaticRouteBuilder = make_builder(StaticRoute)
