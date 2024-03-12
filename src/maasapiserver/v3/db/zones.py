from datetime import datetime
from typing import Any

from sqlalchemy import delete, desc, insert, select, Select
from sqlalchemy.sql.functions import count
from sqlalchemy.sql.operators import eq

from maasapiserver.common.db.tables import DefaultResourceTable, ZoneTable
from maasapiserver.common.models.constants import (
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasapiserver.common.models.exceptions import (
    AlreadyExistsException,
    BaseExceptionDetail,
)
from maasapiserver.v3.api.models.requests.query import PaginationParams
from maasapiserver.v3.api.models.requests.zones import ZoneRequest
from maasapiserver.v3.db.base import BaseRepository
from maasapiserver.v3.models.base import ListResult
from maasapiserver.v3.models.zones import Zone


class ZonesRepository(BaseRepository[Zone, ZoneRequest]):
    async def create(self, request: ZoneRequest) -> Zone:
        check_integrity_stmt = (
            select(ZoneTable.c.id)
            .select_from(ZoneTable)
            .where(eq(ZoneTable.c.name, request.name))
            .limit(1)
        )
        existing_entity = (
            await self.connection.execute(check_integrity_stmt)
        ).one_or_none()
        if existing_entity:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message=f"An entity with name '{request.name}' already exists. Its id is '{existing_entity.id}'.",
                    )
                ]
            )

        now = datetime.utcnow()
        stmt = (
            insert(ZoneTable)
            .returning(
                ZoneTable.c.id,
                ZoneTable.c.name,
                ZoneTable.c.description,
                ZoneTable.c.created,
                ZoneTable.c.updated,
            )
            .values(
                name=request.name,
                description=request.description,
                updated=now,
                created=now,
            )
        )
        result = await self.connection.execute(stmt)
        zone = result.one()
        return Zone(**zone._asdict())

    async def find_by_id(self, id: int) -> Zone | None:
        stmt = self._select_all_statement().filter(eq(ZoneTable.c.id, id))

        result = await self.connection.execute(stmt)
        zone = result.first()
        if not zone:
            return None
        return Zone(**zone._asdict())

    async def find_by_name(self, name: str) -> Zone | None:
        stmt = self._select_all_statement().filter(eq(ZoneTable.c.name, name))

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
            self._select_all_statement()
            .order_by(desc(ZoneTable.c.id))
            .offset((pagination_params.page - 1) * pagination_params.size)
            .limit(pagination_params.size)
        )

        result = await self.connection.execute(stmt)
        return ListResult[Zone](
            items=[Zone(**row._asdict()) for row in result.all()], total=total
        )

    async def update(self, resource: Zone) -> Zone:
        raise Exception("Not implemented yet.")

    async def delete(self, id: int) -> None:
        stmt = delete(ZoneTable).where(eq(ZoneTable.c.id, id))
        await self.connection.execute(stmt)

    async def get_default_zone(self) -> Zone:
        stmt = self._select_all_statement().join(
            DefaultResourceTable,
            eq(DefaultResourceTable.c.zone_id, ZoneTable.c.id),
        )
        result = await self.connection.execute(stmt)
        # By design the default zone is always present.
        zone = result.first()
        return Zone(**zone._asdict())

    def _select_all_statement(self) -> Select[Any]:
        return select(
            ZoneTable.c.id,
            ZoneTable.c.created,
            ZoneTable.c.updated,
            ZoneTable.c.name,
            ZoneTable.c.description,
        ).select_from(ZoneTable)
