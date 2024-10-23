from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.models.domains import Domain
from maasservicelayer.services._base import Service


class DomainsService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        domains_repository: Optional[DomainsRepository] = None,
    ):
        super().__init__(connection)
        self.domains_repository = (
            domains_repository
            if domains_repository
            else DomainsRepository(connection)
        )

    async def get_default_domain(self) -> Domain:
        return await self.domains_repository.get_default_domain()
