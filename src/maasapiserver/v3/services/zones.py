from typing import Optional

from sqlalchemy.ext.asyncio import AsyncConnection

from maasapiserver.common.services._base import Service
from maasapiserver.v3.db.zones import ZonesRepository
from maasapiserver.v3.models.zones import Zone


class ZonesService(Service):
    def __init__(self, connection: AsyncConnection):
        super().__init__(connection)
        self.zones_dao = ZonesRepository(connection)

    async def get_by_id(self, id: int) -> Optional[Zone]:
        return await self.zones_dao.find_by_id(id)
