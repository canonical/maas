# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maasservicelayer.builders.consumers import ConsumerBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.consumers import ConsumersRepository
from maasservicelayer.db.repositories.tokens import TokenClauseFactory
from maasservicelayer.models.consumers import Consumer
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.tokens import TokensService


class ConsumersService(
    BaseService[Consumer, ConsumersRepository, ConsumerBuilder]
):
    """
    Piston3 Consumer service. See
    https://github.com/userzimmermann/django-piston3/blob/fe1ea644bcb07332670aeceddbf0ded29bdf785a/piston/models.py#L55 for
    reference.

    Remove this service once all the django and its OAuth method is removed from the codebase in favor of the new JWT approach.
    """

    def __init__(
        self,
        context: Context,
        repository: ConsumersRepository,
        tokens_service: TokensService,
    ):
        super().__init__(context, repository)
        self.tokens_service = tokens_service

    async def post_delete_hook(self, resource: Consumer) -> None:
        # Cascade
        await self.tokens_service.delete_many(
            query=QuerySpec(
                where=TokenClauseFactory.with_consumer_id(resource.id)
            )
        )

    async def post_delete_many_hook(self, resources: List[Consumer]) -> None:
        # Cascade
        await self.tokens_service.delete_many(
            query=QuerySpec(
                where=TokenClauseFactory.with_consumer_ids(
                    [consumer.id for consumer in resources]
                )
            )
        )
