# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsRepository,
)
from maasservicelayer.models.dhcpsnippets import DhcpSnippet
from maasservicelayer.services._base import Service


class DhcpSnippetsService(Service):
    def __init__(
        self, context: Context, dhcpsnippets_repository: DhcpSnippetsRepository
    ):
        super().__init__(context)
        self.dhcpsnippets_repository = dhcpsnippets_repository

    async def delete(self, query: QuerySpec) -> DhcpSnippet | None:
        return await self.dhcpsnippets_repository.delete(query)
