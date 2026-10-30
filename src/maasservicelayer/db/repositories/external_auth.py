# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import OIDCProviderTable
from maasservicelayer.filters.external_auth import ExternalOAuthFilters
from maasservicelayer.filters.query import QuerySpec
from maasservicelayer.models.external_auth import OAuthProvider


class ExternalOAuthRepository(BaseRepository[OAuthProvider]):
    async def get_provider(self) -> OAuthProvider | None:
        query = QuerySpec(where=ExternalOAuthFilters.with_enabled(True))
        return await self.get_one(query)

    def get_repository_table(self):
        return OIDCProviderTable

    def get_model_factory(self):
        return OAuthProvider
