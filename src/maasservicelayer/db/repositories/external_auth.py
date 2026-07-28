#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.db.filters import Clause, ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import OIDCProviderTable
from maasservicelayer.models.external_auth import OAuthProvider


class ExternalOAuthClauseFactory(ClauseFactory):
    @classmethod
    def with_enabled(cls, enabled: bool) -> Clause:
        return Clause(condition=OIDCProviderTable.c.enabled.is_(enabled))


class ExternalOAuthRepository(BaseRepository[OAuthProvider]):
    async def get_provider(self) -> OAuthProvider | None:
        query = QuerySpec(where=ExternalOAuthClauseFactory.with_enabled(True))
        return await self.get_one(query)

    def get_repository_table(self):
        return OIDCProviderTable

    def get_model_factory(self):
        return OAuthProvider
