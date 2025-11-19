# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from typing import Annotated

from fastapi import Depends, Header, Query, Request, Response
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
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.boot_resources import (
    BootResourceListResponse,
    BootResourceResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.boot_resources import (
    BootResourceFileType,
    BootResourceStrType,
    BootResourceType,
)
from maascommon.workflows.bootresource import (
    ResourceDownloadParam,
    short_sha,
    SYNC_BOOTRESOURCES_WORKFLOW_NAME,
    SyncRequestParam,
)
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.builders.bootresourcefiles import BootResourceFileBuilder
from maasservicelayer.builders.bootresourcefilesync import (
    BootResourceFileSyncBuilder,
)
from maasservicelayer.builders.bootresourcesets import BootResourceSetBuilder
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootresourcefilesync import (
    BootResourceFileSyncClauseFactory,
)
from maasservicelayer.db.repositories.bootresources import (
    BootResourceClauseFactory,
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
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.buffer import ChunkBuffer
from maasservicelayer.utils.date import utcnow
from maasservicelayer.utils.image_local_files import (
    AsyncLocalBootResourceFile,
    LocalStoreAllocationFail,
    LocalStoreFileSizeMismatch,
    LocalStoreInvalidHash,
)
from provisioningserver.utils.env import MAAS_ID

logger = structlog.get_logger()

TYPE_MAPPING = {
    BootResourceStrType.SYNCED: BootResourceType.SYNCED,
    BootResourceStrType.UPLOADED: BootResourceType.UPLOADED,
}


class BootResourcesHandler(Handler):
    """BootResources API handler."""

    TAGS = ["BootResources"]

    CHUNK_SIZE = 4 * 1024 * 1024

    def _get_uploaded_filename(self, filetype: BootResourceFileType) -> str:
        # Root tarball images need to have a proper extension to work for
        # ephemeral deployments.
        filetype_filename = {
            BootResourceFileType.ROOT_TGZ: "root.tgz",
            BootResourceFileType.ROOT_TBZ: "root.tbz",
            BootResourceFileType.ROOT_TXZ: "root.txz",
        }
        return filetype_filename.get(filetype, filetype)

    @handler(
        path="/boot_resources",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": BootResourceResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            400: {"model": BadRequestBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
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
    async def upload_boot_resource(
        self,
        create_request: Annotated[BootResourceCreateRequest, Depends()],
        request: Request,
        response: Response,
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> BootResourceResponse:
        now = utcnow()

        boot_resource = await services.boot_resources.create(
            await create_request.to_builder(services=services)
        )

        version = await services.boot_resources.get_next_version_name(
            boot_resource.id
        )
        resource_set_builder = BootResourceSetBuilder(
            label="uploaded",
            version=version,
            resource_id=boot_resource.id,
            created=now,
            updated=now,
        )

        resource_set = await services.boot_resource_sets.create(
            resource_set_builder
        )

        filename_on_disk = (
            await services.boot_resource_files.calculate_filename_on_disk(
                create_request.sha256
            )
        )

        lfile = AsyncLocalBootResourceFile(
            sha256=create_request.sha256,
            filename_on_disk=filename_on_disk,
            total_size=create_request.size,
        )

        try:
            async with lfile.store() as store:
                # The size of chunks provided below is defined by several factors and can change.
                # Instead we buffer the uploaded data to reduce the number of IO writes and expensive SHA256 updates.
                chunk_buffer = ChunkBuffer(self.CHUNK_SIZE)
                async for chunk in request.stream():
                    needs_flushing = chunk_buffer.append_and_check(chunk)
                    if needs_flushing:
                        await store.write(chunk_buffer.get_and_reset())

                if not chunk_buffer.is_empty():
                    await store.write(chunk_buffer.get_and_reset())

        except LocalStoreAllocationFail as e:
            raise InsufficientStorageException() from e
        except LocalStoreFileSizeMismatch as e:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=f"Provided size does not match the received one. Make sure the file uploaded has a size equal to {create_request.size} bytes.)",
                    )
                ]
            ) from e
        except LocalStoreInvalidHash as e:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_ARGUMENT_VIOLATION_TYPE,
                        message=f"Provided SHA256 does not match calculated one. Make sure the file uploaded has the SHA256 equal to '{create_request.sha256}'",
                    )
                ]
            ) from e

        logger.info(f"Completed upload of file {create_request.name}.")

        resource_filetype = BootResourceFileTypeChoice.get_resource_filetype(
            create_request.file_type
        )

        resource_file_builder = BootResourceFileBuilder(
            extra={},
            filename=self._get_uploaded_filename(resource_filetype),
            filename_on_disk=filename_on_disk,
            filetype=resource_filetype,
            sha256=create_request.sha256,
            size=create_request.size,
            largefile_id=None,
            resource_set_id=resource_set.id,
            created=now,
            updated=now,
        )

        resource_file = await services.boot_resource_files.create(
            resource_file_builder
        )

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
                size=create_request.size,
                region_id=region_info.id,
            ),
        )

        # Trigger a file sync between all regions
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

        response.headers["ETag"] = boot_resource.etag()
        return BootResourceResponse.from_model(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
        )

    @handler(
        path="/boot_resources",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootResourceListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_boot_resources(
        self,
        type: Annotated[
            BootResourceStrType | None,
            Query(description="Filter boot resources of a particular type"),
        ] = None,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootResourceListResponse:
        query_spec = QuerySpec()
        if type:
            query_spec = QuerySpec(
                where=BootResourceClauseFactory.with_rtype(TYPE_MAPPING[type]),
            )
        boot_resources = await services.boot_resources.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=query_spec,
        )
        return BootResourceListResponse(
            items=[
                BootResourceResponse.from_model(
                    boot_resource=boot_resource,
                    self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
                )
                for boot_resource in boot_resources.items
            ],
            total=boot_resources.total,
            next=(
                f"{V3_API_PREFIX}/boot_resources?"
                + f"{pagination_params.to_next_href_format()}"
                if boot_resources.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/boot_resources/{boot_resource_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootResourceResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_boot_resource_by_id(
        self,
        boot_resource_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootResourceResponse:
        boot_resource = await services.boot_resources.get_by_id(
            id=boot_resource_id
        )
        if boot_resource is None:
            raise NotFoundException()
        response.headers["ETag"] = boot_resource.etag()
        return BootResourceResponse.from_model(
            boot_resource=boot_resource,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_resources",
        )

    @handler(
        path="/boot_resources/{boot_resource_id}",
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
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_boot_resource_by_id(
        self,
        boot_resource_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.boot_resources.delete_by_id(
            id=boot_resource_id,
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
