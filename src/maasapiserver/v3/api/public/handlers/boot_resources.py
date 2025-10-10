# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
import hashlib
from typing import Annotated

import aiofiles.os
from aiofiles.tempfile import NamedTemporaryFile
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
from maascommon.utils.images import get_bootresource_store_path
from maascommon.workflows.bootresource import (
    LocalSyncRequestParam,
    ResourceDownloadParam,
    SpaceRequirementParam,
    SYNC_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
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
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_ARGUMENT_VIOLATION_TYPE,
    MISSING_FILE_CONTENT_VIOLATION_TYPE,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.utils.date import utcnow
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

        # LocalBootResourceFile::create_from_content is close to what we need,
        # but we can't stream chunks into it because we need the content ahead of
        # time. And we use aiofiles so as to not block the main thread.
        async with NamedTemporaryFile(
            mode="wb+", dir=get_bootresource_store_path()
        ) as tmp_file:
            sha256 = hashlib.sha256()
            bytes_written = 0

            # The size of chunks provided below is defined by several factors and can change.
            # Instead we buffer the uploaded data to reduce the number of IO writes and expensive SHA256 updates.
            chunk_buffer = bytearray()
            async for chunk in request.stream():
                chunk_buffer.extend(chunk)
                if len(chunk_buffer) >= self.CHUNK_SIZE:
                    sha256.update(chunk_buffer)
                    bytes_written += await tmp_file.write(chunk_buffer)
                    chunk_buffer = bytearray()

            if chunk_buffer:
                sha256.update(chunk_buffer)
                bytes_written += await tmp_file.write(chunk_buffer)

            if bytes_written == 0:
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type=MISSING_FILE_CONTENT_VIOLATION_TYPE,
                            message="No file content provided.",
                        ),
                    ],
                )

            if bytes_written != create_request.size:
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message="Given size parameter does not match provided file size.",
                        )
                    ]
                )

            tmp_filename = str(tmp_file.name)
            tmp_size = await tmp_file.tell()
            tmp_sha256 = sha256.hexdigest()

            if tmp_sha256 != create_request.sha256:
                raise BadRequestException(
                    details=[
                        BaseExceptionDetail(
                            type=INVALID_ARGUMENT_VIOLATION_TYPE,
                            message=f"Provided SHA256 does not match calculated one. Given {create_request.sha256}, calculated {tmp_sha256}.",
                        )
                    ]
                )

            logger.info(
                f"Completed upload of file {create_request.name}. Received {tmp_size} bytes, wrote {bytes_written} bytes - sha256 = '{tmp_sha256}'."
            )

            resource_filetype = (
                BootResourceFileTypeChoice.get_resource_filetype(
                    create_request.file_type
                )
            )

            filename_on_disk = (
                await services.boot_resource_files.calculate_filename_on_disk(
                    tmp_sha256
                )
            )
            resource_file_builder = BootResourceFileBuilder(
                extra={},
                filename=self._get_uploaded_filename(resource_filetype),
                filename_on_disk=filename_on_disk,
                filetype=resource_filetype,
                sha256=tmp_sha256,
                size=tmp_size,
                largefile_id=None,
                resource_set_id=resource_set.id,
                created=now,
                updated=now,
            )

            resource_file = await services.boot_resource_files.create(
                resource_file_builder
            )

            local_resource_file = resource_file.create_local_file()

            await aiofiles.os.rename(tmp_filename, local_resource_file.path)
            logger.info(
                f"Temporary file moved to permanent storage at '{local_resource_file.path}'"
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
                    size=bytes_written,
                    region_id=region_info.id,
                ),
            )

            resource_file_id = resource_file.id
            resource_file_sha256 = resource_file.sha256
            resource_file_name = resource_file.filename_on_disk
            resource_file_size = bytes_written

        # Trigger a file sync between all regions
        sync_request_param = LocalSyncRequestParam(
            resource=ResourceDownloadParam(
                rfile_ids=[resource_file_id],
                source_list=[],
                sha256=resource_file_sha256,
                filename_on_disk=resource_file_name,
                total_size=resource_file_size,
            ),
            space_requirement=SpaceRequirementParam(
                total_resources_size=resource_file_size,
            ),
        )

        services.temporal.register_or_update_workflow_call(
            SYNC_LOCAL_BOOTRESOURCES_WORKFLOW_NAME,
            sync_request_param,
            workflow_id=f"sync-local-bootresource:{resource_file_id}",
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
