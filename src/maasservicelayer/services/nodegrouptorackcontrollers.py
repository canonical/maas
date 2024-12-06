# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersRepository,
)
from maasservicelayer.models.nodegrouptorackcontrollers import (
    NodeGroupToRackController,
)
from maasservicelayer.services._base import BaseService


class NodeGroupToRackControllersService(
    BaseService[
        NodeGroupToRackController, NodeGroupToRackControllersRepository
    ]
):
    def __init__(
        self,
        context: Context,
        nodegrouptorackcontrollers_repository: NodeGroupToRackControllersRepository,
    ):
        super().__init__(context, nodegrouptorackcontrollers_repository)