# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from maascommon.enums.node import NodeStatus
from maasservicelayer.models.base import MaasTimestampedBaseModel


class Node(MaasTimestampedBaseModel):
    # TODO: model to be completed.
    system_id: str
    status: NodeStatus
