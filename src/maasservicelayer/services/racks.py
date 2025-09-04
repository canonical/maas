# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maasservicelayer.builders.racks import RackBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.agents import AgentsClauseFactory
from maasservicelayer.db.repositories.bootstraptokens import (
    BootstrapTokensClauseFactory,
)
from maasservicelayer.db.repositories.racks import RacksRepository
from maasservicelayer.models.racks import Rack
from maasservicelayer.services.agents import AgentsService
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.bootstraptoken import BootstrapTokensService


class RacksService(BaseService[Rack, RacksRepository, RackBuilder]):
    def __init__(
        self,
        context: Context,
        repository: RacksRepository,
        agents_service: AgentsService,
        bootstraptokens_service: BootstrapTokensService,
    ) -> None:
        super().__init__(context, repository)
        self.agents_service = agents_service
        self.bootstraptokens_service = bootstraptokens_service

    async def post_delete_hook(self, resource: Rack) -> None:
        # cascade delete for a single resource
        await self.bootstraptokens_service.delete_many(
            query=QuerySpec(
                where=BootstrapTokensClauseFactory.with_rack_id(resource.id)
            )
        )
        await self.agents_service.delete_many(
            query=QuerySpec(
                where=AgentsClauseFactory.with_rack_id(resource.id)
            )
        )

    async def post_delete_many_hook(self, resources: List[Rack]) -> None:
        # cascade delete for multiple resources
        rack_ids = [resource.id for resource in resources]

        await self.bootstraptokens_service.delete_many(
            query=QuerySpec(
                where=BootstrapTokensClauseFactory.with_rack_id_in(rack_ids)
            )
        )
        await self.agents_service.delete_many(
            query=QuerySpec(
                where=AgentsClauseFactory.with_rack_id_in(rack_ids)
            )
        )
