# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from pydantic import IPvAnyAddress
from sqlalchemy import and_, cast, select, Table
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql.expression import exists
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.mappers.reservedips import ReservedIPDataMapper
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import ReservedIPTable
from maasservicelayer.models.reservedips import ReservedIP


class ReservedIPsRepository(BaseRepository[ReservedIP]):
    def get_mapper(self) -> ReservedIPDataMapper:
        return ReservedIPDataMapper(ReservedIP, ReservedIPTable)

    def get_repository_table(self) -> Table:
        return ReservedIPTable

    def get_model_factory(self) -> Type[ReservedIP]:
        return ReservedIP

    async def exists_within_subnet_ip_range(
        self, subnet_id: int, start_ip: IPvAnyAddress, end_ip: IPvAnyAddress
    ) -> bool:
        stmt = select(1).where(
            and_(
                eq(ReservedIPTable.c.subnet_id, subnet_id),
                cast(ReservedIPTable.c.ip, INET).between(start_ip, end_ip),
            )
        )
        stmt = exists(stmt).select()
        return bool((await self.execute_stmt(stmt)).scalar())
