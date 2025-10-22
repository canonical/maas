# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from base64 import b64decode

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
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
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsources import (
    BootSourcesClauseFactory,
)
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.exceptions.catalog import NotFoundException
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
    async def list_boot_sources(
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
    async def get_boot_source(
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
    async def create_boot_source(
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
    async def update_boot_source(
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
    async def delete_boot_source(
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
    async def fetch_boot_sources_available_images(
        self,
        request: BootSourceFetchRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> SourceAvailableImageListResponse:
        # Base64 decode keyring data (if present) so we can write the bytes to file later.
        keyring_data_bytes = None
        if request.keyring_data:
            keyring_data_bytes = b64decode(request.keyring_data)

        images = await services.image_sync.fetch_image_metadata(
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
    async def list_boot_source_boot_source_selection(
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
    async def get_boot_source_boot_source_selection(
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
    async def create_boot_source_boot_source_selection(
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
    async def update_boot_source_boot_source_selection(
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
    async def delete_boot_source_boot_source_selection(
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
    async def get_boot_source_available_images(
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
