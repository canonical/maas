#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import desc, select, Table

from maasservicelayer.db.repositories.base import (
    BaseRepository,
    CreateOrUpdateResourceBuilder,
)
from maasservicelayer.db.tables import DNSPublicationTable
from maasservicelayer.models.dnspublications import DNSPublication


class DNSPublicationResourceBuilder(CreateOrUpdateResourceBuilder):
    def with_serial(self, serial: int) -> "DNSPublicationResourceBuilder":
        self._request.set_value(DNSPublicationTable.c.serial.name, serial)
        return self

    def with_source(self, source: str) -> "DNSPublicationResourceBuilder":
        self._request.set_value(DNSPublicationTable.c.source.name, source)
        return self

    def with_update(self, update: str) -> "DNSPublicationResourceBuilder":
        self._request.set_value(DNSPublicationTable.c.update_str.name, update)
        return self


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

        result = (await self.connection.execute(stmt)).first()

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

        result = (await self.connection.execute(stmt)).all()

        return [DNSPublication(**row._asdict()) for row in result]
