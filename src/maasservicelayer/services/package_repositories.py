# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maascommon.enums.events import EventTypeEnum
from maasservicelayer.builders.package_repositories import (
    PackageRepositoryBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.package_repositories import (
    PackageRepositoriesRepository,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_PACKAGE_REPO_VIOLATION_TYPE,
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.package_repositories import PackageRepository
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.events import EventsService


class PackageRepositoriesService(
    BaseService[
        PackageRepository,
        PackageRepositoriesRepository,
        PackageRepositoryBuilder,
    ]
):
    def __init__(
        self,
        context: Context,
        repository: PackageRepositoriesRepository,
        events_service: EventsService,
        cache: ServiceCache | None = None,
    ):
        self.events_service = events_service
        super().__init__(context, repository, cache)

    async def post_create_hook(self, resource: PackageRepository) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.SETTINGS,
            event_description=f"Created package repository {resource.name}",
        )

    async def post_update_hook(
        self,
        old_resource: PackageRepository,
        updated_resource: PackageRepository,
    ) -> None:
        if old_resource.default and (
            old_resource.arches != updated_resource.arches
        ):
            # see LP: #2110140
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="Architectures for default package repositories cannot be updated.",
                    )
                ]
            )
        await self.events_service.record_event(
            event_type=EventTypeEnum.SETTINGS,
            event_description=f"Updated package repository {updated_resource.name}",
        )

    async def post_update_many_hook(
        self, resources: List[PackageRepository]
    ) -> None:
        raise NotImplementedError()

    async def pre_delete_hook(
        self, resource_to_be_deleted: PackageRepository
    ) -> None:
        main = await self.get_main_archive()
        ports = await self.get_ports_archive()
        if resource_to_be_deleted.id in (main.id, ports.id):
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=CANNOT_DELETE_DEFAULT_PACKAGE_REPO_VIOLATION_TYPE,
                        message="Default package repositories cannot be deleted.",
                    )
                ]
            )

    async def post_delete_hook(self, resource: PackageRepository) -> None:
        await self.events_service.record_event(
            event_type=EventTypeEnum.SETTINGS,
            event_description=f"Deleted package repository {resource.name}",
        )

    async def post_delete_many_hook(
        self, resources: List[PackageRepository]
    ) -> None:
        raise NotImplementedError()

    async def get_main_archive(self) -> PackageRepository:
        return await self.repository.get_main_archive()

    async def get_ports_archive(self) -> PackageRepository:
        return await self.repository.get_ports_archive()
