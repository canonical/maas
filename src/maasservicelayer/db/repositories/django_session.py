# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from maasservicelayer.builders.django_session import DjangoSessionBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import SessionTable
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.django_session import DjangoSession


class DjangoSessionRepository(Repository):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mapper = DefaultDomainDataMapper(SessionTable)

    async def create(self, builder: DjangoSessionBuilder) -> DjangoSession:
        resource = self.mapper.build_resource(builder)
        stmt = (
            insert(SessionTable)
            .returning(SessionTable)
            .values(**resource.get_values())
        )
        try:
            result = (await self.execute_stmt(stmt)).one()
            return DjangoSession(**result._asdict())
        except IntegrityError as e:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exist.",
                    )
                ]
            ) from e

    async def get_by_session_key(
        self, session_key: str
    ) -> DjangoSession | None:
        stmt = (
            select(SessionTable)
            .select_from(SessionTable)
            .where(eq(SessionTable.c.session_key, session_key))
        )
        session = (await self.execute_stmt(stmt)).one_or_none()
        if session:
            return DjangoSession(**session._asdict())
        return None

    async def update_by_session_key(
        self, session_key: str, builder: DjangoSessionBuilder
    ) -> DjangoSession:
        resource = self.mapper.build_resource(builder)
        stmt = (
            update(SessionTable)
            .returning(SessionTable)
            .where(eq(SessionTable.c.session_key, session_key))
            .values(**resource.get_values())
        )
        result = (await self.execute_stmt(stmt)).one_or_none()
        if not result:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Resource with such identifiers does not exist.",
                    )
                ]
            )
        return DjangoSession(**result._asdict())

    async def delete_by_session_key(self, session_key: str) -> None:
        stmt = delete(SessionTable).where(
            eq(SessionTable.c.session_key, session_key)
        )
        await self.execute_stmt(stmt)
