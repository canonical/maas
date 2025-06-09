#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import desc, select, Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DNSPublicationTable
from maasservicelayer.models.dnspublications import DNSPublication


class DNSPublicationRepository(BaseRepository[DNSPublication]):
    def get_repository_table(self) -> Table:
        return DNSPublicationTable

    def get_model_factory(self) -> Type[DNSPublication]:
        return DNSPublication

    async def get_latest_serial(self) -> int:
        stmt = (
            select(DNSPublicationTable.c.serial)
            .select_from(DNSPublicationTable)
            .order_by(desc(DNSPublicationTable.c.id))
        )

        result = (await self.execute_stmt(stmt)).first()

        assert result is not None
        return result[0]

    async def get_publications_since_serial(
        self, serial: int
    ) -> list[DNSPublication]:
        stmt = (
            select(DNSPublicationTable)
            .select_from(DNSPublicationTable)
            .filter(
                DNSPublicationTable.c.serial > serial,
            )
        )

        result = (await self.execute_stmt(stmt)).all()

        return [DNSPublication(**row._asdict()) for row in result]

    async def get_latest(self) -> DNSPublication:
        stmt = (
            select(DNSPublicationTable)
            .select_from(DNSPublicationTable)
            .order_by(DNSPublicationTable.c.id.desc())
        )

        result = (await self.execute_stmt(stmt)).first()
        assert result is not None
        return DNSPublication(**result._asdict())
