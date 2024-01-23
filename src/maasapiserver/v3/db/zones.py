from datetime import datetime
from typing import Any, Optional

from sqlalchemy import desc, insert, select, Select
from sqlalchemy.sql.functions import count

from maasapiserver.common.db.tables import ZoneTable
from maasapiserver.common.models.exceptions import (
    AlreadyExistsException,
    BaseExceptionDetail,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
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
            .where(ZoneTable.c.name == request.name)
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

    async def find_by_id(self, id: int) -> Optional[Zone]:
        stmt = self._select_all_statement().filter(ZoneTable.c.id == id)

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

    async def update(self, id: str, request: ZoneRequest) -> Zone:
        pass

    async def delete(self) -> None:
        pass

    async def _raise_if_already_existing(self, request: ZoneRequest):
        check_integrity_stmt = (
            select(ZoneTable.c.id)
            .select_from(ZoneTable)
            .where(ZoneTable.c.name == request.name)
            .limit(1)
        )
        existing_entity = await self.connection.execute(check_integrity_stmt)
        if existing_entity:
            AlreadyExistsException()

    def _select_all_statement(self) -> Select[Any]:
        return select(
            ZoneTable.c.id,
            ZoneTable.c.created,
            ZoneTable.c.updated,
            ZoneTable.c.name,
            ZoneTable.c.description,
        ).select_from(ZoneTable)
