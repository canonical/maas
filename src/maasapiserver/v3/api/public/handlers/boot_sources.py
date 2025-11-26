# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode

from fastapi import Depends, Header, Response, status
from fastapi.openapi.models import Header as OpenApiHeader
from fastapi.openapi.models import Schema
from fastapi.responses import RedirectResponse
from temporalio.client import WorkflowExecutionStatus

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
    BootSourceSelectionFilterParams,
    BootSourceSelectionRequest,
)
from maasapiserver.v3.api.public.models.requests.boot_sources import (
    BootSourceFetchRequest,
    BootSourceRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.boot_source_selections import (
    BootSourceSelectionListResponse,
    BootSourceSelectionResponse,
    BootSourceSelectionStatusListResponse,
    BootSourceSelectionStatusResponse,
    BootSourceSelectionSyncResponse,
)
from maasapiserver.v3.api.public.models.responses.boot_sources import (
    BootSourceAvailableImageListResponse,
    BootSourceAvailableImageResponse,
    BootSourceResponse,
    BootSourcesListResponse,
    SourceAvailableImageListResponse,
    SourceAvailableImageResponse,
    UISourceAvailableImageListResponse,
    UISourceAvailableImageResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.workflows.bootresource import (
    SYNC_SELECTION_WORKFLOW_NAME,
    SyncSelectionParam,
)
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    ConflictException,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import CONFLICT_VIOLATION_TYPE
from maasservicelayer.models.bootsourceselections import (
    SelectionStatus,
    SelectionUpdateStatus,
)
from maasservicelayer.services import ServiceCollectionV3


class BootSourcesHandler(Handler):
    """BootSources API handler."""

    TAGS = ["BootSources"]

    @handler(
        path="/boot_sources",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourcesListResponse,
            }
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_bootsources(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourcesListResponse:
        boot_sources = await services.boot_sources.list(
            page=pagination_params.page, size=pagination_params.size
        )
        return BootSourcesListResponse(
            items=[
                BootSourceResponse.from_model(
                    boot_source=boot_source,
                    self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources",
                )
                for boot_source in boot_sources.items
            ],
            total=boot_sources.total,
            next=(
                f"{V3_API_PREFIX}/boot_sources?"
                f"{pagination_params.to_next_href_format()}"
                if boot_sources.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/boot_sources/{boot_source_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourceResponse,
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
    async def get_bootsource(
        self,
        boot_source_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceResponse:
        boot_source = await services.boot_sources.get_by_id(boot_source_id)
        if boot_source is None:
            raise NotFoundException()
        response.headers["ETag"] = boot_source.etag()
        return BootSourceResponse.from_model(
            boot_source=boot_source,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources",
        )

    @handler(
        path="/boot_sources",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": BootSourceResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_bootsource(
        self,
        boot_source_request: BootSourceRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceResponse:
        builder = boot_source_request.to_builder()
        boot_source = await services.boot_sources.create(builder)
        response.headers["ETag"] = boot_source.etag()
        return BootSourceResponse.from_model(
            boot_source=boot_source,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources",
        )

    @handler(
        path="/boot_sources/{boot_source_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourceResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_bootsource(
        self,
        boot_source_id: int,
        boot_source_request: BootSourceRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceResponse:
        builder = boot_source_request.to_builder()
        boot_source = await services.boot_sources.update_by_id(
            boot_source_id, builder
        )
        response.headers["ETag"] = boot_source.etag()
        return BootSourceResponse.from_model(
            boot_source=boot_source,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources",
        )

    @handler(
        path="/boot_sources/{boot_source_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_bootsource(
        self,
        boot_source_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.boot_sources.delete_by_id(boot_source_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/boot_sources:fetch",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": SourceAvailableImageListResponse,
            },
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def fetch_bootsources_available_images(
        self,
        request: BootSourceFetchRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SourceAvailableImageListResponse:
        # Base64 decode keyring data (if present) so we can write the bytes to file later.
        keyring_data_bytes = None
        if request.keyring_data:
            keyring_data_bytes = b64decode(request.keyring_data)

        images = await services.image_manifests.fetch_image_metadata(
            source_url=request.url,
            keyring_path=request.keyring_path,
            keyring_data=keyring_data_bytes,
        )
        # The fetch method isn't paginated, so we return all items
        # in a single response.
        return SourceAvailableImageListResponse(
            items=[
                SourceAvailableImageResponse.from_model(image)
                for image in images
            ]
        )

    @handler(
        path="/boot_sources/{boot_source_id}/selections",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": BootSourceSelectionListResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceSelectionListResponse:
        boot_source_selections = await services.boot_source_selections.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.with_boot_source_id(
                    boot_source_id
                )
            ),
        )
        if not boot_source_selections:
            raise NotFoundException()

        return BootSourceSelectionListResponse(
            items=[
                BootSourceSelectionResponse.from_model(
                    boot_source_selection=boot_source_selection,
                    self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/selections/",
                )
                for boot_source_selection in boot_source_selections.items
            ],
            next=(
                f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/selections?"
                f"{pagination_params.to_next_href_format()}"
                if boot_source_selections.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
            total=boot_source_selections.total,
        )

    @handler(
        path="/boot_sources/{boot_source_id}/selections/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourceSelectionResponse,
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
    async def get_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceSelectionResponse:
        boot_source_selection = await services.boot_source_selections.get_one(
            QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_id(id),
                        BootSourceSelectionClauseFactory.with_boot_source_id(
                            boot_source_id
                        ),
                    ]
                )
            )
        )
        if not boot_source_selection:
            raise NotFoundException()

        response.headers["ETag"] = boot_source_selection.etag()
        return BootSourceSelectionResponse.from_model(
            boot_source_selection=boot_source_selection,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/selections/",
        )

    @handler(
        path="/boot_sources/{boot_source_id}/selections",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {"model": BootSourceSelectionResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        boot_source_selection_request: BootSourceSelectionRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceSelectionResponse:
        boot_source = await services.boot_sources.get_one(
            query=QuerySpec(
                where=BootSourcesClauseFactory.with_id(boot_source_id)
            )
        )
        if not boot_source:
            raise NotFoundException()

        builder = boot_source_selection_request.to_builder(boot_source)
        boot_source_selection = await services.boot_source_selections.create(
            builder
        )

        return BootSourceSelectionResponse.from_model(
            boot_source_selection=boot_source_selection,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/selections",
        )

    @handler(
        path="/boot_sources/{boot_source_id}/selections/{id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourceResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        id: int,
        boot_source_selection_request: BootSourceSelectionRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        boot_source = await services.boot_sources.get_by_id(boot_source_id)
        if not boot_source:
            raise NotFoundException()

        builder = boot_source_selection_request.to_builder(boot_source)
        boot_source_selection = (
            await services.boot_source_selections.update_by_id(id, builder)
        )

        response.headers["ETag"] = boot_source_selection.etag()
        return BootSourceSelectionResponse.from_model(
            boot_source_selection=boot_source_selection,
            self_base_hyperlink=f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/selections",
        )

    @handler(
        path="/boot_sources/{boot_source_id}/selections/{id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        query = QuerySpec(
            where=BootSourceSelectionClauseFactory.and_clauses(
                [
                    BootSourceSelectionClauseFactory.with_id(id),
                    BootSourceSelectionClauseFactory.with_boot_source_id(
                        boot_source_id
                    ),
                ]
            )
        )
        await services.boot_source_selections.delete_one(
            query=query,
            etag_if_match=etag_if_match,
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/boot_sources/{boot_source_id}/selections/{id}:sync",
        methods=["POST"],
        tags=TAGS,
        responses={
            202: {
                "model": BootSourceSelectionSyncResponse,
            },
            303: {
                "headers": {
                    "Location": OpenApiHeader(
                        description="URL to monitor the synchronization status",
                        schema=Schema(type="string", format="uri"),
                    )
                },
            },
            404: {"model": NotFoundBodyResponse},
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=202,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def sync_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceSelectionSyncResponse:
        boot_source_selection = await services.boot_source_selections.get_one(
            QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_id(id),
                        BootSourceSelectionClauseFactory.with_boot_source_id(
                            boot_source_id
                        ),
                    ]
                )
            )
        )
        if not boot_source_selection:
            raise NotFoundException()

        selection_status = (
            await services.boot_source_selection_status.get_by_id(
                boot_source_selection.id
            )
        )

        assert selection_status is not None
        if selection_status.selected is False:
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=CONFLICT_VIOLATION_TYPE,
                        message="Only the selected boot source selections can be synchronized.",
                    )
                ]
            )
        elif (
            selection_status.status == SelectionStatus.READY
            and selection_status.update_status
            == SelectionUpdateStatus.NO_UPDATES_AVAILABLE
        ):
            raise ConflictException(
                details=[
                    BaseExceptionDetail(
                        type=CONFLICT_VIOLATION_TYPE,
                        message="The boot source selection is already up to date.",
                    )
                ]
            )

        monitor_url = f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/selections/{boot_source_selection.id}:check_status"
        status = await services.temporal.workflow_status(
            f"{SYNC_SELECTION_WORKFLOW_NAME}:{boot_source_selection.id}"
        )
        if status == WorkflowExecutionStatus.RUNNING:
            return RedirectResponse(monitor_url, status_code=303)  # pyright: ignore[reportReturnType]

        wf_id = f"{SYNC_SELECTION_WORKFLOW_NAME}:{boot_source_selection.id}"
        services.temporal.register_workflow_call(
            workflow_name=SYNC_SELECTION_WORKFLOW_NAME,
            workflow_id=wf_id,
            parameter=SyncSelectionParam(boot_source_selection.id),
            wait=False,
        )
        return BootSourceSelectionSyncResponse(monitor_url=monitor_url)

    @handler(
        path="/boot_sources/{boot_source_id}/selections/{id}:stop_sync",
        methods=["POST"],
        tags=TAGS,
        responses={
            202: {},
            404: {"model": NotFoundBodyResponse},
            409: {"model": ConflictBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=202,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def stop_sync_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        boot_source_selection = await services.boot_source_selections.get_one(
            QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_id(id),
                        BootSourceSelectionClauseFactory.with_boot_source_id(
                            boot_source_id
                        ),
                    ]
                )
            )
        )
        if not boot_source_selection:
            raise NotFoundException()

        status = await services.temporal.workflow_status(
            f"{SYNC_SELECTION_WORKFLOW_NAME}:{boot_source_selection.id}"
        )
        wf_id = f"{SYNC_SELECTION_WORKFLOW_NAME}:{boot_source_selection.id}"
        if status == WorkflowExecutionStatus.RUNNING:
            temporal_client = await services.temporal.get_temporal_client()
            await temporal_client.get_workflow_handle(wf_id).cancel()
            return Response(status_code=202)

        raise ConflictException(
            details=[
                BaseExceptionDetail(
                    type=CONFLICT_VIOLATION_TYPE,
                    message="Selection is not being synchronized.",
                )
            ]
        )

    @handler(
        path="/boot_sources/{boot_source_id}/selections/{id}:check_status",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": BootSourceSelectionStatusResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def check_status_bootsource_bootsourceselection(
        self,
        boot_source_id: int,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceSelectionStatusResponse:
        boot_source_selection = await services.boot_source_selections.get_one(
            QuerySpec(
                where=BootSourceSelectionClauseFactory.and_clauses(
                    [
                        BootSourceSelectionClauseFactory.with_id(id),
                        BootSourceSelectionClauseFactory.with_boot_source_id(
                            boot_source_id
                        ),
                    ]
                )
            )
        )
        if not boot_source_selection:
            raise NotFoundException()

        status = await services.boot_source_selection_status.get_by_id(
            boot_source_selection.id
        )

        assert status is not None
        return BootSourceSelectionStatusResponse.from_model(status)

    @handler(
        path="/boot_source_selection_statuses",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": BootSourceSelectionStatusResponse,
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def check_statuses_bootsource_bootsourceselection(
        self,
        ids: BootSourceSelectionFilterParams = Depends(),  # noqa: B008
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceSelectionStatusListResponse:
        statuses = await services.boot_source_selection_status.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=ids.to_clause()),
        )

        next_link = None
        if statuses.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/boot_source_selection_statuses?"
                f"{pagination_params.to_next_href_format()}"
            )
            if query_filters := ids.to_href_format():
                next_link += f"&{query_filters}"

        return BootSourceSelectionStatusListResponse(
            items=[
                BootSourceSelectionStatusResponse.from_model(status)
                for status in statuses.items
            ],
            next=next_link,
            total=statuses.total,
        )

    @handler(
        path="/available_images",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": UISourceAvailableImageListResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_all_available_images(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> UISourceAvailableImageListResponse:
        boot_source_available_images = (
            await services.boot_source_cache.get_all_available_images()
        )

        items: list[UISourceAvailableImageResponse] = []
        for boot_source_available_image in boot_source_available_images:
            boot_source = await services.boot_sources.get_by_id(
                boot_source_available_image.boot_source_id
            )
            assert boot_source is not None

            items.append(
                UISourceAvailableImageResponse.from_model(
                    boot_source=boot_source,
                    boot_source_available_image=boot_source_available_image,
                )
            )

        return UISourceAvailableImageListResponse(items=items)

    @handler(
        path="/boot_sources/{boot_source_id}/available_images",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": BootSourceAvailableImageListResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_bootsource_available_images(
        self,
        boot_source_id: int,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> BootSourceAvailableImageListResponse:
        boot_source = await services.boot_sources.get_by_id(boot_source_id)
        if not boot_source:
            raise NotFoundException()

        boot_source_available_images = await services.boot_source_cache.list_boot_source_cache_available_images(
            page=pagination_params.page,
            size=pagination_params.size,
            boot_source_id=boot_source_id,
        )

        return BootSourceAvailableImageListResponse(
            items=[
                BootSourceAvailableImageResponse.from_model(
                    boot_source_available_image=boot_source_available_image,
                )
                for boot_source_available_image in boot_source_available_images.items
            ],
            next=(
                f"{V3_API_PREFIX}/boot_sources/{boot_source_id}/available_images?"
                f"{pagination_params.to_next_href_format()}"
                if boot_source_available_images.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
            total=boot_source_available_images.total,
        )
