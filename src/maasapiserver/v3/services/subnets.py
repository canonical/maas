# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.subnets import SubnetsRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.subnets import Subnet


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
