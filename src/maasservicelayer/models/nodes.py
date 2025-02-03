# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from datetime import datetime
from typing import Optional

from maascommon.enums.node import NodeStatus
from maascommon.enums.power import PowerState
from maasservicelayer.models.base import (
    generate_builder,
    MaasTimestampedBaseModel,
)


@generate_builder()
class Node(MaasTimestampedBaseModel):
    # TODO: model to be completed.
    system_id: str
    status: NodeStatus
    power_state: PowerState
    power_state_updated: datetime | None
    owner_id: Optional[int] = None
    current_commissioning_script_set_id: int | None = None
    current_testing_script_set_id: int | None = None
    current_installation_script_set_id: int | None = None
