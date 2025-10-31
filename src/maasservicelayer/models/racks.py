# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maasservicelayer.models.base import (
    BaseModel,
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Rack(MaasTimestampedBaseModel):
    name: str


class RackWithSummary(BaseModel):
    id: int
    name: str
    registered_agents_system_ids: List[str]
