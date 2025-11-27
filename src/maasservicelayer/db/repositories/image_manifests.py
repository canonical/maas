# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Iterable

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from maasservicelayer.builders.image_manifests import ImageManifestBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import ImageManifestTable
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.image_manifests import ImageManifest


class ImageManifestsRepository(Repository):
    def __init__(self, context: Context):
        super().__init__(context)
        self.mapper = DefaultDomainDataMapper(ImageManifestTable)

    async def get(self, boot_source_id: int) -> ImageManifest | None:
        stmt = (
            select(ImageManifestTable)
            .select_from(ImageManifestTable)
            .where(eq(ImageManifestTable.c.boot_source_id, boot_source_id))
        )

        result = (await self.execute_stmt(stmt)).one_or_none()
        if result:
            return ImageManifest(**result._asdict())
        return None

    async def create(self, builder: ImageManifestBuilder) -> ImageManifest:
        resource = self.mapper.build_resource(builder)
        stmt = (
            insert(ImageManifestTable)
            .returning(ImageManifestTable)
            .values(**resource.get_values())
        )
        try:
            result = (await self.execute_stmt(stmt)).one()
            return ImageManifest(**result._asdict())
        except IntegrityError as e:
            raise AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exist.",
                    )
                ]
            ) from e

    async def update(self, builder: ImageManifestBuilder) -> ImageManifest:
        boot_source_id = builder.ensure_set(builder.boot_source_id)
        resource = self.mapper.build_resource(builder)
        stmt = (
            update(ImageManifestTable)
            .returning(ImageManifestTable)
            .where(eq(ImageManifestTable.c.boot_source_id, boot_source_id))
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
        return ImageManifest(**result._asdict())

    async def delete_many_by_boot_source_ids(
        self, boot_source_ids: Iterable[int]
    ) -> None:
        ids = set(boot_source_ids)
        if not ids:
            return
        stmt = delete(ImageManifestTable).where(
            ImageManifestTable.c.boot_source_id.in_(ids)
        )
        await self.execute_stmt(stmt)

    async def delete(self, boot_source_id: int) -> None:
        stmt = delete(ImageManifestTable).where(
            eq(ImageManifestTable.c.boot_source_id, boot_source_id)
        )
        await self.execute_stmt(stmt)
