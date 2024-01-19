from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.sql.functions import count

from maasapiserver.common.db.tables import ZoneTable
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
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

    async def list(
        self, pagination_params: PaginationParams
    ) -> ListResult[Zone]:
        total_stmt = select(count()).select_from(ZoneTable)
        # There is always at least one "default" zone being created at first startup during the migrations.
        total = (await self.connection.execute(total_stmt)).scalar()

        stmt = (
            select(
                ZoneTable.c.id,
                ZoneTable.c.created,
                ZoneTable.c.updated,
                ZoneTable.c.name,
                ZoneTable.c.description,
            )
            .select_from(ZoneTable)
            .order_by(desc(ZoneTable.c.id))
            .offset((pagination_params.page - 1) * pagination_params.size)
            .limit(pagination_params.size)
        )

        result = await self.connection.execute(stmt)
        return ListResult[Zone](
            items=[Zone(**row._asdict()) for row in result.all()], total=total
        )

    async def get(self) -> Zone:
        pass

    async def delete(self) -> None:
        pass

    async def update(self) -> Zone:
        pass
