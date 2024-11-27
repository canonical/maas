# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersRepository,
)
from maasservicelayer.models.nodegrouptorackcontrollers import (
    NodeGroupToRackController,
)
from maasservicelayer.services._base import Service


class NodeGroupToRackControllersService(Service):
    def __init__(
        self,
        context: Context,
        nodegrouptorackcontrollers_repository: NodeGroupToRackControllersRepository,
    ):
        super().__init__(context)
        self.nodegrouptorackcontrollers_repository = (
            nodegrouptorackcontrollers_repository
        )

    async def delete(
        self, query: QuerySpec
    ) -> NodeGroupToRackController | None:
        return await self.nodegrouptorackcontrollers_repository.delete(query)
