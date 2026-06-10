# Copyright 2025-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated, NoReturn

from fastapi import Depends, Header, Query, Request, Response
from pydantic import Field
from starlette import status
import structlog

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadRequestBodyResponse,
    NotFoundBodyResponse,
    PreconditionFailedBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.boot_resources import (
    BootResourceCreateRequest,
    BootResourceFileTypeChoice,
    CustomImageFilterParams,
    CustomImageTypeChoice,
    validate_architecture,
    validate_boot_asset_name,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageListResponse,
    ImageResponse,
    ImageStatisticListResponse,
    ImageStatisticResponse,
    ImageStatusListResponse,
    ImageStatusResponse,
)
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootAssetUploadResponse,
    BootloaderListResponse,
    BootloaderResponse,
    KernelListResponse,
    KernelResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceType,
)
from maascommon.openfga.base import MAASResourceEntitlement
from maascommon.workflows.bootresource import (
    ResourceDownloadParam,
    short_sha,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasservicelayer.builders.bootresourcefilesync import (
    BootResourceFileSyncBuilder,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncClauseFactory,
)
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
)
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetClauseFactory,
)
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    BaseExceptionDetail,
    InsufficientStorageException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
)
from maasservicelayer.models.fields import UniqueList
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.buffer import ChunkBuffer
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.image_local_files import (
    AsyncLocalBootResourceFile,
    LocalStoreAllocationFail,
    LocalStoreInvalidHash,
)
from provisioningserver.utils.env import MAAS_ID

logger = structlog.get_logger()


class CustomImagesHandler(Handler):
    """CustomImages API handler."""

    TAGS = ["CustomImages"]

    CHUNK_SIZE = 4 * 1024 * 1024

    def get_handlers(self):
        return [
            "list_custom_images_status",
            "get_custom_image_status",
            "list_custom_images_statistic",
            "get_custom_image_statistic",
            "upload_custom_image",
            "upload_bootloader",
            "upload_kernel",
            "upload_kernel_initrd",
            "list_custom_images",
            "get_custom_image_by_id",
            "bulk_delete_custom_images",
            "delete_custom_image_by_id",
        ]

    def _get_uploaded_filename(self, filetype: BootResourceFileType) -> str:
        # Root tarball images need to have a proper extension to work for
        # ephemeral deployments.
        filetype_filename = {
            BootResourceFileType.ROOT_TGZ: "root.tgz",
            BootResourceFileType.ROOT_TBZ: "root.tbz",
            BootResourceFileType.ROOT_TXZ: "root.txz",
            BootResourceFileType.SELF_EXTRACTING: "installer.bin",
        }
        return filetype_filename.get(filetype, filetype)

    def _raise_bad_request(self, message: str) -> NoReturn:
        raise BadRequestException(
            details=[
                BaseExceptionDetail(
                    type=INVALID_ARGUMENT_VIOLATION_TYPE,
                    message=message,
                )
            ]
        )

    async def _stream_to_disk(
        self,
        stream: AsyncGenerator[bytes, None],
        sha256: str,
        total_size: int,
        services: ServiceCollectionV3,
    ) -> str:
        """Stream bytes to the boot resource store, return filename_on_disk."""
        filename_on_disk = (
            await services.boot_resource_files.calculate_filename_on_disk(
                sha256
            )
        )
        lfile = AsyncLocalBootResourceFile(
            sha256=sha256,
            filename_on_disk=filename_on_disk,
            total_size=total_size,
        )
        try:
            async with lfile.store() as store:
                chunk_buffer = ChunkBuffer(self.CHUNK_SIZE)
                async for chunk in stream:
                    if chunk_buffer.append_and_check(chunk):
                        await store.write(chunk_buffer.get_and_reset())
                if not chunk_buffer.is_empty():
                    await store.write(chunk_buffer.get_and_reset())
        except LocalStoreAllocationFail as e:
            raise InsufficientStorageException() from e
        except LocalStoreInvalidHash as e:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=f"SHA256 mismatch: expected {sha256}",
                    )
                ]
            ) from e
        return filename_on_disk

    async def _trigger_sync_workflow(
        self,
        resource_file,
        services: ServiceCollectionV3,
    ) -> None:
        """Create BootResourceFileSync record and trigger sync workflow."""
        now = utcnow()
        maas_system_id = await asyncio.to_thread(lambda: MAAS_ID.get())
        assert maas_system_id is not None

        region_info = await services.nodes.get_one(
            query=QuerySpec(
                where=NodeClauseFactory.with_system_id(maas_system_id),
            )
        )
        assert region_info is not None

        await services.boot_resource_file_sync.get_or_create(
            query=QuerySpec(
                where=BootResourceFileSyncClauseFactory.with_file_id(
                    resource_file.id
                ),
            ),
            builder=BootResourceFileSyncBuilder(
                created=now,
                updated=now,
                file_id=resource_file.id,
                size=resource_file.size,
                region_id=region_info.id,
            ),
        )

        sync_request_param = SyncRequestParam(
            resource=ResourceDownloadParam(
                rfile_ids=[resource_file.id],
                source_list=[],
                sha256=resource_file.sha256,
                filename_on_disk=resource_file.filename_on_disk,
                total_size=resource_file.size,
            ),
        )

        services.temporal.register_or_update_workflow_call(
            SYNC_BOOTRESOURCES_WORKFLOW_NAME,
            sync_request_param,
            workflow_id=f"sync-bootresources:{short_sha(resource_file.sha256)}",
            wait=False,
        )

    async def _build_boot_asset_upload_response(
        self,
        boot_resource_id: int,
        version: str,
        services: ServiceCollectionV3,
    ) -> list[dict[str, str | int]]:
        resource_set = await services.boot_resource_sets.get_one(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(
                            boot_resource_id
                        ),
                        BootResourceSetClauseFactory.with_version(version),
                    ]
                )
            )
        )
        assert resource_set is not None
        files = await services.boot_resource_files.get_files_in_resource_set(
            resource_set.id
        )
        return [
            {
                "filename": file.filename,
                "filetype": str(file.filetype),
                "sha256": file.sha256,
                "size": file.size,
            }
            for file in files
        ]

    async def _trigger_sync_for_version(
        self,
        boot_resource_id: int,
        version: str,
        services: ServiceCollectionV3,
    ) -> None:
        resource_set = await services.boot_resource_sets.get_one(
            query=QuerySpec(
                where=BootResourceSetClauseFactory.and_clauses(
                    [
                        BootResourceSetClauseFactory.with_resource_id(
                            boot_resource_id
                        ),
                        BootResourceSetClauseFactory.with_version(version),
                    ]
                )
            )
        )
        if resource_set is not None:
            for (
                file_obj
            ) in await services.boot_resource_files.get_files_in_resource_set(
                resource_set.id
            ):
                await self._trigger_sync_workflow(file_obj, services)

    @handler(
        path="/custom_images",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": ImageResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            400: {"model": BadRequestBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES
                )
            )
        ],
        openapi_extra={
            "requestBody": {
                "description": "Image content, presented as an `application/octet-stream` file upload.",
                "required": True,
                "content": {
                    "application/octet-stream": {
                        "schema": {
                            "type": "string",
                            "format": "binary",
                        },
                    },
                },
            }
        },
    )
    async def upload_custom_image(
        self,
        create_request: Annotated[BootResourceCreateRequest, Header()],
        request: Request,
        response: Response,
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> ImageResponse:
        file_size = int(request.headers["content-length"])
        builder = await create_request.to_builder(services=services)

        resource_filetype = BootResourceFileTypeChoice.get_resource_filetype(
            create_request.file_type
        )
        filename = self._get_uploaded_filename(resource_filetype)
        filename_on_disk = await self._stream_to_disk(
            request.stream(), create_request.sha256, file_size, services
        )

        logger.info(f"Completed upload of file {create_request.name}.")

        (
            boot_resource,
            resource_file,
        ) = await services.boot_resources.upload_custom_image(
            name=builder.name,  # pyright: ignore[reportArgumentType]
            architecture=builder.architecture,  # pyright: ignore[reportArgumentType]
            sha256=create_request.sha256,
            filetype=resource_filetype,
            filename=filename,
            filename_on_disk=filename_on_disk,
            size=file_size,
            base_image=builder.base_image,  # pyright: ignore[reportArgumentType]
            extra=builder.extra,  # pyright: ignore[reportArgumentType]
        )

        await self._trigger_sync_workflow(resource_file, services)

        response.headers["ETag"] = boot_resource.etag()
        return ImageResponse.from_boot_resource(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
        )

    @handler(
        path="/boot_assets/bootloaders",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {"model": BootAssetUploadResponse},
            400: {"model": BadRequestBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES
                )
            )
        ],
        openapi_extra={
            "requestBody": {
                "description": "Bootloader file content as `application/octet-stream`.",
                "required": True,
                "content": {
                    "application/octet-stream": {
                        "schema": {
                            "type": "string",
                            "format": "binary",
                        },
                    },
                },
            }
        },
    )
    async def upload_bootloader(
        self,
        request: Request,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootAssetUploadResponse:
        name = request.headers.get("x-name")
        architecture = request.headers.get("x-architecture")
        sha256 = request.headers.get("x-sha256")
        primary_file = request.headers.get("x-primary-file")

        if not name:
            self._raise_bad_request("x-name header is required")
        if not architecture:
            self._raise_bad_request("x-architecture header is required")
        if not sha256:
            self._raise_bad_request("x-sha256 header is required")
        if not primary_file:
            self._raise_bad_request("x-primary-file header is required")

        name = await validate_boot_asset_name(name, services)
        architecture = await validate_architecture(architecture, services)
        file_size = int(request.headers["content-length"])
        filename_on_disk = await self._stream_to_disk(
            request.stream(), sha256, file_size, services
        )

        (
            boot_resource,
            version,
        ) = await services.boot_resources.upload_bootloader(
            name=name,
            architecture=architecture,
            sha256=sha256,
            primary_file=primary_file,
            filename_on_disk=filename_on_disk,
            size=file_size,
        )
        files = await self._build_boot_asset_upload_response(
            boot_resource.id, version, services
        )
        await self._trigger_sync_for_version(
            boot_resource.id, version, services
        )

        return BootAssetUploadResponse.from_model(
            boot_resource=boot_resource,
            version=version,
            files=files,
            self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
        )

    @handler(
        path="/boot_assets/kernels",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {"model": BootAssetUploadResponse},
            400: {"model": BadRequestBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES
                )
            )
        ],
        openapi_extra={
            "requestBody": {
                "description": "Kernel file content as `application/octet-stream`.",
                "required": True,
                "content": {
                    "application/octet-stream": {
                        "schema": {
                            "type": "string",
                            "format": "binary",
                        },
                    },
                },
            }
        },
    )
    async def upload_kernel(
        self,
        request: Request,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootAssetUploadResponse:
        name = request.headers.get("x-name")
        architecture = request.headers.get("x-architecture")
        kflavor = request.headers.get("x-kflavor")
        sha256 = request.headers.get("x-sha256")

        if not name:
            self._raise_bad_request("x-name header is required")
        if not architecture:
            self._raise_bad_request("x-architecture header is required")
        if not kflavor:
            self._raise_bad_request("x-kflavor header is required")
        if not sha256:
            self._raise_bad_request("x-sha256 header is required")

        name = await validate_boot_asset_name(name, services)
        architecture = await validate_architecture(architecture, services)
        file_size = int(request.headers["content-length"])
        filename_on_disk = await self._stream_to_disk(
            request.stream(), sha256, file_size, services
        )

        (
            boot_resource,
            version,
        ) = await services.boot_resources.upload_kernel(
            name=name,
            architecture=architecture,
            kflavor=kflavor,
            sha256=sha256,
            filename_on_disk=filename_on_disk,
            size=file_size,
        )
        files = await self._build_boot_asset_upload_response(
            boot_resource.id, version, services
        )
        await self._trigger_sync_for_version(
            boot_resource.id, version, services
        )

        return BootAssetUploadResponse.from_model(
            boot_resource=boot_resource,
            version=version,
            files=files,
            self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
        )

    @handler(
        path="/boot_assets/kernels/{resource_id}/initrd",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {"model": BootAssetUploadResponse},
            400: {"model": BadRequestBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES
                )
            )
        ],
        openapi_extra={
            "requestBody": {
                "description": "Initrd file content as `application/octet-stream`.",
                "required": True,
                "content": {
                    "application/octet-stream": {
                        "schema": {
                            "type": "string",
                            "format": "binary",
                        },
                    },
                },
            }
        },
    )
    async def upload_kernel_initrd(
        self,
        resource_id: int,
        request: Request,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootAssetUploadResponse:
        sha256 = request.headers.get("x-sha256")

        if not sha256:
            self._raise_bad_request("x-sha256 header is required")

        file_size = int(request.headers["content-length"])
        filename_on_disk = await self._stream_to_disk(
            request.stream(), sha256, file_size, services
        )

        (
            boot_resource,
            version,
        ) = await services.boot_resources.upload_kernel_initrd(
            resource_id=resource_id,
            sha256=sha256,
            filename_on_disk=filename_on_disk,
            size=file_size,
        )
        files = await self._build_boot_asset_upload_response(
            boot_resource.id, version, services
        )
        await self._trigger_sync_for_version(
            boot_resource.id, version, services
        )

        return BootAssetUploadResponse.from_model(
            boot_resource=boot_resource,
            version=version,
            files=files,
            self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
        )

    @handler(
        path="/custom_images",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def list_custom_images(
        self,
        asset_type: Annotated[
            CustomImageTypeChoice | None,
            Query(
                alias="type",
                description="Filter by asset type.",
            ),
        ] = None,
        name: Annotated[
            str | None,
            Query(description="Filter by asset name."),
        ] = None,
        architecture: Annotated[
            str | None,
            Query(description="Filter by architecture."),
        ] = None,
        kflavor: Annotated[
            str | None,
            Query(description="Filter by kernel flavor."),
        ] = None,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageListResponse:
        # When no type filter is given, return all uploaded resources.
        # When a type is specified, the per-type clause already embeds the
        # rtype=UPLOADED constraint, so with_uploaded_type() is not applied
        # separately to avoid redundancy.
        clauses = [
            asset_type.to_clause()
            if asset_type is not None
            else BootResourceClauseFactory.with_uploaded_type()
        ]
        if name is not None:
            clauses.append(BootResourceClauseFactory.with_name(name))
        if architecture is not None:
            clauses.append(
                BootResourceClauseFactory.with_architecture(architecture)
            )
        if kflavor is not None:
            clauses.append(BootResourceClauseFactory.with_kflavor(kflavor))

        query_clause = (
            BootResourceClauseFactory.and_clauses(clauses)
            if len(clauses) > 1
            else clauses[0]
        )

        boot_resources = await services.boot_resources.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=query_clause),
        )

        next_link = None
        if boot_resources.has_next(
            pagination_params.page, pagination_params.size
        ):
            next_link = (
                f"{V3_API_PREFIX}/custom_images?"
                f"{pagination_params.to_next_href_format()}"
            )
            if asset_type is not None:
                next_link += f"&type={asset_type.value}"
            if name is not None:
                next_link += f"&name={name}"
            if architecture is not None:
                next_link += f"&architecture={architecture}"
            if kflavor is not None:
                next_link += f"&kflavor={kflavor}"

        return ImageListResponse(
            items=[
                ImageResponse.from_boot_resource(
                    boot_resource=boot_resource,
                    self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
                )
                for boot_resource in boot_resources.items
            ],
            total=boot_resources.total,
            next=next_link,
        )

    @handler(
        path="/custom_images/{boot_resource_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def get_custom_image_by_id(
        self,
        boot_resource_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageResponse:
        boot_resource = await services.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_id(boot_resource_id),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
        )
        if boot_resource is None:
            raise NotFoundException()
        response.headers["ETag"] = boot_resource.etag()
        return ImageResponse.from_boot_resource(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/custom_images",
        )

    @handler(
        path="/custom_images/{boot_resource_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
            412: {"model": PreconditionFailedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES
                )
            )
        ],
    )
    async def delete_custom_image_by_id(
        self,
        boot_resource_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.boot_resources.delete_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_id(boot_resource_id),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/custom_images",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
            412: {"model": PreconditionFailedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES
                )
            )
        ],
    )
    async def bulk_delete_custom_images(
        self,
        ids: Annotated[
            UniqueList[int],
            Field(min_length=1),
        ] = Query(  # noqa: B008
            description="ids of custom images to delete", alias="id"
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.boot_resources.delete_many(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_ids(ids),
                        BootResourceClauseFactory.with_rtype(
                            BootResourceType.UPLOADED
                        ),
                    ]
                )
            ),
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/custom_images/statuses",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageStatusListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def list_custom_images_status(
        self,
        filters: CustomImageFilterParams = Depends(),  # noqa: B008
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatusListResponse:
        statuses = await services.boot_resources.list_custom_images_status(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=filters.to_clause()),
        )

        next_link = None
        if statuses.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/custom_images/statuses?"
                f"{pagination_params.to_next_href_format()}"
            )
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"

        return ImageStatusListResponse(
            items=[
                ImageStatusResponse.from_model(status)
                for status in statuses.items
            ],
            next=next_link,
            total=statuses.total,
        )

    @handler(
        path="/custom_images/statuses/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageStatusResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def get_custom_image_status(
        self,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatusResponse:
        status = await services.boot_resources.get_custom_image_status_by_id(
            id
        )
        if not status:
            raise NotFoundException()

        return ImageStatusResponse.from_model(status)

    @handler(
        path="/custom_images/statistics",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageStatisticListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def list_custom_images_statistic(
        self,
        filters: CustomImageFilterParams = Depends(),  # noqa: B008
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatisticListResponse:
        statistics = (
            await services.boot_resources.list_custom_images_statistics(
                page=pagination_params.page,
                size=pagination_params.size,
                query=QuerySpec(where=filters.to_clause()),
            )
        )

        next_link = None
        if statistics.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/custom_images/statistics?"
                f"{pagination_params.to_next_href_format()}"
            )
            if query_filters := filters.to_href_format():
                next_link += f"&{query_filters}"

        return ImageStatisticListResponse(
            items=[
                ImageStatisticResponse.from_model(statistic)
                for statistic in statistics.items
            ],
            next=next_link,
            total=statistics.total,
        )

    @handler(
        path="/custom_images/statistics/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageStatisticResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def get_custom_image_statistic(
        self,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatisticResponse:
        statistic = (
            await services.boot_resources.get_custom_image_statistic_by_id(id)
        )
        if not statistic:
            raise NotFoundException()

        return ImageStatisticResponse.from_model(statistic)


class BootloadersHandler(Handler):
    """Bootloaders API handler."""

    TAGS = ["Bootloaders"]

    @handler(
        path="/boot_assets/bootloaders",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootloaderListResponse,
            }
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def list_bootloaders(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootloaderListResponse:
        bootloaders = await services.boot_resources.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(
                where=BootResourceClauseFactory.not_clause(
                    BootResourceClauseFactory.with_bootloader_type(None)
                )
            ),
        )
        resource_ids = [b.id for b in bootloaders.items]
        versions_map = (
            await services.boot_resources.get_versions_for_resources(
                resource_ids
            )
        )
        files_map = await services.boot_resources.get_files_for_latest_sets(
            resource_ids
        )
        base = f"{V3_API_PREFIX}/boot_assets/bootloaders"
        return BootloaderListResponse(
            items=[
                BootloaderResponse.from_model(
                    boot_resource=bootloader,
                    self_base_hyperlink=base,
                    versions=versions_map.get(bootloader.id, []),
                    resource_files=files_map.get(bootloader.id, []),
                )
                for bootloader in bootloaders.items
            ],
            total=bootloaders.total,
            next=(
                f"{base}?{pagination_params.to_next_href_format()}"
                if bootloaders.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/boot_assets/bootloaders/{bootloader_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootloaderResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def get_bootloader(
        self,
        bootloader_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootloaderResponse:
        bootloader = await services.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.not_clause(
                            BootResourceClauseFactory.with_bootloader_type(
                                None
                            )
                        ),
                        BootResourceClauseFactory.with_id(bootloader_id),
                    ]
                )
            )
        )
        if bootloader is None:
            raise NotFoundException()
        response.headers["ETag"] = bootloader.etag()
        versions_map = (
            await services.boot_resources.get_versions_for_resources(
                [bootloader.id]
            )
        )
        files_map = await services.boot_resources.get_files_for_latest_sets(
            [bootloader.id]
        )
        base = f"{V3_API_PREFIX}/boot_assets/bootloaders"
        return BootloaderResponse.from_model(
            boot_resource=bootloader,
            self_base_hyperlink=base,
            versions=versions_map.get(bootloader.id, []),
            resource_files=files_map.get(bootloader.id, []),
        )


class KernelsHandler(Handler):
    """Kernels API handler."""

    TAGS = ["Kernels"]

    @handler(
        path="/boot_assets/kernels",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": KernelListResponse,
            }
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def list_kernels(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        name: str | None = Query(default=None),  # noqa: B008
        architecture: str | None = Query(default=None),  # noqa: B008
        kflavor: str | None = Query(default=None),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> KernelListResponse:
        clauses = [BootResourceClauseFactory.with_asset_type_kernel()]
        if name is not None:
            clauses.append(BootResourceClauseFactory.with_name(name))
        if architecture is not None:
            clauses.append(
                BootResourceClauseFactory.with_architecture(architecture)
            )
        if kflavor is not None:
            clauses.append(BootResourceClauseFactory.with_kflavor(kflavor))
        where = (
            BootResourceClauseFactory.and_clauses(clauses)
            if len(clauses) > 1
            else clauses[0]
        )
        kernels = await services.boot_resources.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=where),
        )
        resource_ids = [k.id for k in kernels.items]
        versions_map = (
            await services.boot_resources.get_versions_for_resources(
                resource_ids
            )
        )
        files_map = await services.boot_resources.get_files_for_latest_sets(
            resource_ids
        )
        extra_params = ""
        if name is not None:
            extra_params += f"&name={name}"
        if architecture is not None:
            extra_params += f"&architecture={architecture}"
        if kflavor is not None:
            extra_params += f"&kflavor={kflavor}"
        return KernelListResponse(
            items=[
                KernelResponse.from_model(
                    boot_resource=kernel,
                    self_base_hyperlink=f"{V3_API_PREFIX}/boot_assets/kernels",
                    versions=versions_map.get(kernel.id, []),
                    resource_files=files_map.get(kernel.id, []),
                )
                for kernel in kernels.items
            ],
            total=kernels.total,
            next=(
                f"{V3_API_PREFIX}/boot_assets/kernels?"
                f"{pagination_params.to_next_href_format()}{extra_params}"
                if kernels.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/boot_assets/kernels/{kernel_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": KernelResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES
                )
            )
        ],
    )
    async def get_kernel(
        self,
        kernel_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> KernelResponse:
        kernel = await services.boot_resources.get_one(
            query=QuerySpec(
                where=BootResourceClauseFactory.and_clauses(
                    [
                        BootResourceClauseFactory.with_asset_type_kernel(),
                        BootResourceClauseFactory.with_id(kernel_id),
                    ]
                )
            )
        )
        if kernel is None:
            raise NotFoundException()
        response.headers["ETag"] = kernel.etag()
        versions_map = (
            await services.boot_resources.get_versions_for_resources(
                [kernel.id]
            )
        )
        files_map = await services.boot_resources.get_files_for_latest_sets(
            [kernel.id]
        )
        return KernelResponse.from_model(
            boot_resource=kernel,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_assets/kernels",
            versions=versions_map.get(kernel.id, []),
            resource_files=files_map.get(kernel.id, []),
        )
