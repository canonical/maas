# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.db.repositories.subnets import SubnetsRepository
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service


class SubnetsService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        subnets_repository: SubnetsRepository | None = None,
    ):
        super().__init__(connection)
        self.subnets_repository = (
            subnets_repository
            if subnets_repository
            else SubnetsRepository(connection)
        )

    async def list(self, token: str | None, size: int) -> ListResult[Subnet]:
        return await self.subnets_repository.list(token=token, size=size)

    async def get_by_id(self, id: int) -> Subnet | None:
        return await self.subnets_repository.find_by_id(id=id)

    async def find_best_subnet_for_ip(self, ip: str) -> Subnet | None:
        return await self.subnets_repository.find_best_subnet_for_ip(ip)
