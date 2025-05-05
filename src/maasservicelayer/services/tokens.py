# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.tokens import TokenBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.tokens import TokensRepository
from maasservicelayer.models.tokens import Token
from maasservicelayer.services.base import BaseService


class TokensService(BaseService[Token, TokensRepository, TokenBuilder]):
    """
    Piston3 Token service. See
    https://github.com/userzimmermann/django-piston3/blob/fe1ea644bcb07332670aeceddbf0ded29bdf785a/piston/models.py#L55 for
    reference.

    Remove this service once all the django and its OAuth method is removed from the codebase in favor of the new JWT approach.
    """

    def __init__(self, context: Context, repository: TokensRepository):
        super().__init__(context, repository)

    async def get_user_apikeys(self, username: str) -> list[str]:
        return await self.repository.get_user_apikeys(username)
