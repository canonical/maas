from typing import Optional

from sqlalchemy import select

from maasapiserver.common.db.tables import ZoneTable
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.zones import Zone


class ZonesRepository(BaseRepository[Zone]):
    async def find_by_id(self, id: int) -> Optional[Zone]:
        stmt = (
            select(
                ZoneTable.c.id,
                ZoneTable.c.created,
                ZoneTable.c.updated,
                ZoneTable.c.name,
                ZoneTable.c.description,
            )
            .select_from(ZoneTable)
            .filter(ZoneTable.c.id == id)
        )

        result = await self.connection.execute(stmt)
        zone = result.first()
        if not zone:
            return None
        return Zone(**zone._asdict())

    async def list(self, pagination_params: PaginationParams) -> list[Zone]:
        pass

    async def get(self) -> Zone:
        pass

    async def delete(self) -> None:
        pass

    async def update(self) -> Zone:
        pass
