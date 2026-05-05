# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from typing import Literal

import structlog

from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maasservicelayer.builders.bootresourcefiles import BootResourceFileBuilder
from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.builders.bootresourcesets import BootResourceSetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
    BootResourcesRepository,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.bootresourcefiles import BootResourceFile
from maasservicelayer.models.bootresources import (
    BootResource,
    CustomBootResourceStatistic,
    CustomBootResourceStatus,
)
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.base import BaseService, ServiceCache
from maasservicelayer.services.bootresourcefiles import (
    BootResourceFilesService,
)
from maasservicelayer.services.bootresourcesets import BootResourceSetsService
from maasservicelayer.utils.date import utcnow

logger = structlog.get_logger()


class BootResourceService(
    BaseService[BootResource, BootResourcesRepository, BootResourceBuilder]
):
    resource_logging_name = "bootresources"

    def __init__(
        self,
        context: Context,
        repository: BootResourcesRepository,
        boot_resource_sets_service: BootResourceSetsService,
        boot_resource_files_service: BootResourceFilesService,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
        self.boot_resource_sets_service = boot_resource_sets_service
        self.boot_resource_files_service = boot_resource_files_service

    async def pre_delete_hook(
        self, resource_to_be_deleted: BootResource
    ) -> None:
        await self.boot_resource_sets_service.delete_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_id(
                    resource_to_be_deleted.id
                )
            )
        )

    async def pre_delete_many_hook(
        self, resources: list[BootResource]
    ) -> None:
        await self.boot_resource_sets_service.delete_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_ids(
                    [r.id for r in resources]
                )
            )
        )

    async def delete_all_without_sets(
        self, query: QuerySpec
    ) -> list[BootResource]:
        """Delete all the boot resources that don't have an associated resource set."""
        boot_resources = await self.get_many(query=query)
        boot_resources_ids = {b.id for b in boot_resources}
        all_resource_sets = await self.boot_resource_sets_service.get_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_ids(
                    list(boot_resources_ids)
                )
            )
        )
        boot_resource_ids_with_sets = {
            rset.resource_id for rset in all_resource_sets
        }
        boot_resource_ids_without_sets = (
            boot_resources_ids - boot_resource_ids_with_sets
        )

        return await self.delete_many(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_ids(
                    boot_resource_ids_without_sets
                )
            )
        )

    async def get_usable_architectures(self) -> list[str]:
        """Return the set of usable architectures.

        Return the architectures for which the resource has at least one
        commissioning image and at least one install image.
        """
        architectures: set[str] = set()

        all_boot_resources = await self.get_many(query=QuerySpec())
        for boot_resource in all_boot_resources:
            latest_resource_set = await self.boot_resource_sets_service.get_latest_complete_set_for_boot_resource(
                boot_resource.id
            )
            if not latest_resource_set:
                continue

            is_usable = await self.boot_resource_sets_service.is_usable(
                latest_resource_set.id
            )
            is_xinstallable = (
                await self.boot_resource_sets_service.is_xinstallable(
                    latest_resource_set.id
                )
            )
            if latest_resource_set and is_usable and is_xinstallable:
                if (
                    "hwe-" not in boot_resource.architecture
                    and "ga-" not in boot_resource.architecture
                ):
                    architectures.add(boot_resource.architecture)

                arch, _ = boot_resource.split_arch()

                if "subarches" in boot_resource.extra:
                    for subarch in boot_resource.extra["subarches"].split(","):
                        if "hwe-" not in subarch and "ga-" not in subarch:
                            architectures.add(f"{arch}/{subarch.strip()}")
                if "platform" in boot_resource.extra:
                    architectures.add(
                        f"{arch}/{boot_resource.extra['platform']}"
                    )
                if "supported_platforms" in boot_resource.extra:
                    for platform in boot_resource.extra[
                        "supported_platforms"
                    ].split(","):
                        architectures.add(f"{arch}/{platform}")

        return sorted(architectures)

    async def get_next_version_name(self, boot_resource_id: int) -> str:
        version_name = utcnow().strftime("%Y%m%d")

        sets_for_boot_resource = (
            await self.boot_resource_sets_service.get_many(
                query=QuerySpec(
                    where=BootResourceSetClauseFactory.and_clauses(
                        [
                            BootResourceSetClauseFactory.with_resource_id(
                                boot_resource_id
                            ),
                            BootResourceSetClauseFactory.with_version_prefix(
                                version_name
                            ),
                        ]
                    )
                ),
            )
        )
        if not sets_for_boot_resource:
            return version_name

        max_idx = 0
        for resource_set in sets_for_boot_resource:
            if "." in resource_set.version:
                _, set_idx = resource_set.version.split(".")
                set_idx = int(set_idx)
                if set_idx > max_idx:
                    max_idx = set_idx

        return "%s.%d" % (version_name, max_idx + 1)

    async def get_custom_image_status_by_id(
        self, id: int
    ) -> CustomBootResourceStatus | None:
        return await self.repository.get_custom_image_status_by_id(id)

    async def list_custom_images_status(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[CustomBootResourceStatus]:
        return await self.repository.list_custom_images_status(
            page=page, size=size, query=query
        )

    async def get_custom_image_statistic_by_id(
        self, id: int
    ) -> CustomBootResourceStatistic | None:
        return await self.repository.get_custom_image_statistic_by_id(id)

    async def list_custom_images_statistics(
        self, page: int, size: int, query: QuerySpec | None = None
    ) -> ListResult[CustomBootResourceStatistic]:
        return await self.repository.list_custom_images_statistics(
            page=page, size=size, query=query
        )

    async def upload_custom_image(
        self,
        name: str,
        architecture: str,
        sha256: str,
        filetype: BootResourceFileType,
        filename: str,
        filename_on_disk: str,
        size: int,
        base_image: str,
        extra: dict[str, object],
    ) -> tuple[BootResource, BootResourceFile]:
        """Create DB records for an uploaded custom image.

        The file must already be written to the boot resource store by the
        caller before invoking this method.
        """
        existing = await self.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_name(name),
                        BootResourceClauseFactory.with_architecture(
                            architecture
                        ),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            )
        )

        now = utcnow()
        if existing is None:
            boot_resource = await self.create(
                BootResourceBuilder(
                    alias="",
                    architecture=architecture,
                    base_image=base_image,
                    bootloader_type=None,
                    extra=extra,
                    kflavor=None,
                    name=name,
                    rolling=False,
                    rtype=BootResourceType.UPLOADED,
                    last_deployed=None,
                    created=now,
                    updated=now,
                )
            )
        else:
            boot_resource = existing

        version = await self.get_next_version_name(boot_resource.id)
        resource_set = await self.boot_resource_sets_service.create(
            BootResourceSetBuilder(
                label="uploaded",
                version=version,
                resource_id=boot_resource.id,
                created=now,
                updated=now,
            )
        )

        resource_file = await self.boot_resource_files_service.create(
            BootResourceFileBuilder(
                extra=extra,
                filename=filename,
                filename_on_disk=filename_on_disk,
                filetype=filetype,
                sha256=sha256,
                size=size,
                largefile_id=None,
                resource_set_id=resource_set.id,
                created=now,
                updated=now,
            )
        )

        return boot_resource, resource_file

    async def upload_bootloader(
        self,
        name: str,
        architecture: str,
        sha256: str,
        primary_file: str,
        filename_on_disk: str,
        size: int,
    ) -> tuple[BootResource, str]:
        """Create DB records for a custom bootloader tarball.

        The file must already be written to the boot resource store by the
        caller before invoking this method. primary_file names the EFI binary
        within the tarball that DHCP's filename option should point to.
        """
        boot_resource = await self.repository.find_or_create_bootloader(
            name, architecture
        )
        version = await self.get_next_version_name(boot_resource.id)

        now = utcnow()
        resource_set = await self.boot_resource_sets_service.create(
            BootResourceSetBuilder(
                label="uploaded",
                version=version,
                resource_id=boot_resource.id,
                created=now,
                updated=now,
            )
        )

        await self.boot_resource_files_service.create(
            BootResourceFileBuilder(
                extra={"primary_file": primary_file},
                filename="bootloader.tar.gz",
                filename_on_disk=filename_on_disk,
                filetype=BootResourceFileType.BOOTLOADER_TARBALL,
                sha256=sha256,
                size=size,
                largefile_id=None,
                resource_set_id=resource_set.id,
                created=now,
                updated=now,
            )
        )

        return boot_resource, version

    async def upload_kernel(
        self,
        name: str,
        architecture: str,
        kflavor: str,
        sha256: str,
        filename_on_disk: str,
        size: int,
    ) -> tuple[BootResource, str]:
        """Create DB records for a custom kernel (without initrd).

        The file must already be written to the boot resource store by the
        caller before invoking this method.
        """
        boot_resource = await self.repository.find_or_create_kernel(
            name, architecture, kflavor
        )
        version = await self.get_next_version_name(boot_resource.id)

        now = utcnow()
        resource_set = await self.boot_resource_sets_service.create(
            BootResourceSetBuilder(
                label="uploaded",
                version=version,
                resource_id=boot_resource.id,
                created=now,
                updated=now,
            )
        )

        await self.boot_resource_files_service.create(
            BootResourceFileBuilder(
                extra={},
                filename="kernel",
                filename_on_disk=filename_on_disk,
                filetype=BootResourceFileType.BOOT_KERNEL,
                sha256=sha256,
                size=size,
                largefile_id=None,
                resource_set_id=resource_set.id,
                created=now,
                updated=now,
            )
        )

        return boot_resource, version

    async def upload_kernel_initrd(
        self,
        resource_id: int,
        sha256: str,
        filename_on_disk: str,
        size: int,
    ) -> tuple[BootResource, str]:
        """Append an initrd file to an existing kernel boot resource.

        The file must already be written to the boot resource store by the
        caller before invoking this method.
        """
        boot_resource = await self.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.with_id(resource_id)
            )
        )
        if boot_resource is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=f"Boot resource {resource_id} not found",
                    )
                ]
            )

        resource_sets = await self.boot_resource_sets_service.get_many(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.with_resource_id(
                    boot_resource.id
                )
            )
        )
        if not resource_sets:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=(
                            f"No resource set found for boot resource "
                            f"{resource_id}"
                        ),
                    )
                ]
            )

        resource_set = max(resource_sets, key=lambda s: s.id)
        version = resource_set.version

        now = utcnow()
        await self.boot_resource_files_service.create(
            BootResourceFileBuilder(
                extra={},
                filename="initrd",
                filename_on_disk=filename_on_disk,
                filetype=BootResourceFileType.BOOT_INITRD,
                sha256=sha256,
                size=size,
                largefile_id=None,
                resource_set_id=resource_set.id,
                created=now,
                updated=now,
            )
        )

        return boot_resource, version

    async def resolve_boot_asset_for_deployment(
        self,
        name: str,
        architecture: str,
        kflavor: str | None = None,
        asset_type: Literal["bootloader", "kernel"] = "bootloader",
    ) -> BootResourceSet:
        if asset_type == "bootloader":
            boot_resource = (
                await self.repository.get_bootloader_for_architecture(
                    name, architecture
                )
            )
        else:
            if kflavor is None:
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message="kflavor is required when asset_type is 'kernel'",
                        )
                    ]
                )
            boot_resource = await self.get_one(
                query=QuerySpec(
                    where=BootResourceClauseFactory.with_kernel_identity(
                        name, architecture, kflavor
                    )
                )
            )

        if boot_resource is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="Requested boot asset was not found",
                    )
                ]
            )

        latest_set = await self.repository.get_latest_version(boot_resource.id)
        if latest_set is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message="Requested boot asset has no uploaded versions",
                    )
                ]
            )
        return latest_set

    async def get_bootloader_path_for_machine(
        self,
        _machine_id: int,
        bootloader_name: str,
        architecture: str,
    ) -> str | None:
        boot_resource = await self.repository.get_bootloader_for_architecture(
            bootloader_name, architecture
        )
        if boot_resource is None:
            return None

        latest_set = await self.repository.get_latest_version(boot_resource.id)
        if latest_set is None:
            return None

        bootloader_file = await self.repository.get_bootloader_file_for_set(
            latest_set.id
        )
        if bootloader_file is None:
            return None

        primary_file = bootloader_file.extra.get("primary_file")
        if not primary_file:
            logger.warning(
                "Bootloader resource has no primary_file in extra; cannot resolve DHCP path",
                bootloader_name=bootloader_name,
                architecture=architecture,
                resource_set_id=latest_set.id,
            )
            return None

        # Compute the versioned extraction directory on the Rack.
        # Uses __ as separator since name and architecture contain slashes.
        safe_name = bootloader_name.replace("/", "__")
        safe_arch = architecture.replace("/", "__")
        extract_dir = (
            f"bootloaders/{safe_name}/{safe_arch}/{latest_set.version}"
        )
        return f"{extract_dir}/{primary_file}"

    async def resolve_bootloader_for_deployment(
        self,
        bootloader_name: str,
        architecture: str,
    ) -> BootResourceSet:
        """Resolve a custom bootloader for deployment.

        Validates that the named bootloader exists and has an uploaded version
        for the given architecture. The caller is responsible for triggering
        any DHCP reconfiguration after updating machine metadata.
        """
        return await self.resolve_boot_asset_for_deployment(
            name=bootloader_name,
            architecture=architecture,
            asset_type="bootloader",
        )
