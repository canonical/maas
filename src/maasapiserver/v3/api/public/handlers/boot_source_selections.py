# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Depends, Query, Response
from fastapi.exceptions import RequestValidationError
from pydantic import conlist, ValidationError
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
    BootSourceSelectionStatisticFilterParams,
    BootSourceSelectionStatusFilterParams,
    BulkSelectionRequest,
    SelectionRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageListResponse,
    ImageResponse,
    ImageStatisticListResponse,
    ImageStatisticResponse,
    ImageStatusListResponse,
    ImageStatusResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionClauseFactory,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3


class BootSourceSelectionsHandler(Handler):
    """BootSourceSelections handler."""

    TAGS = ["BootSourceSelections"]

    @handler(
        path="/selections",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ImageListResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_selections(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageListResponse:
        boot_source_selections = await services.boot_source_selections.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )

        return ImageListResponse(
            items=[
                ImageResponse.from_selection(
                    selection=boot_source_selection,
                    self_base_hyperlink=f"{V3_API_PREFIX}/selections",
                )
                for boot_source_selection in boot_source_selections.items
            ],
            next=(
                f"{V3_API_PREFIX}/selections?"
                f"{pagination_params.to_next_href_format()}"
                if boot_source_selections.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
            total=boot_source_selections.total,
        )

    @handler(
        path="/selections/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ImageResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_selection(
        self,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageResponse:
        boot_source_selection = (
            await services.boot_source_selections.get_by_id(id)
        )
        if not boot_source_selection:
            raise NotFoundException()
        return ImageResponse.from_selection(
            selection=boot_source_selection,
            self_base_hyperlink=f"{V3_API_PREFIX}/selections/{id}",
        )

    @handler(
        path="/selections",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {"model": ImageListResponse},
            409: {"model": ConflictBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def bulk_create_selections(
        self,
        selections_to_create: list[SelectionRequest],
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageListResponse:
        # we don't use BulkSelectionRequest directly because we want to pass a
        # list of selections in the body, rather than passing {"selections":[...]}
        try:
            bulk_create_request = BulkSelectionRequest(
                selections=selections_to_create
            )
        except ValidationError as e:
            raise RequestValidationError(errors=e.errors()) from None
        builders = bulk_create_request.get_builders()
        boot_source_selections = (
            await services.boot_source_selections.create_many(builders)
        )
        return ImageListResponse(
            items=[
                ImageResponse.from_selection(
                    selection=boot_source_selection,
                    self_base_hyperlink=f"{V3_API_PREFIX}/selections",
                )
                for boot_source_selection in boot_source_selections
            ],
            next=None,
            total=len(boot_source_selections),
        )

    @handler(
        path="/selections",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
        },
        status_code=204,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def bulk_delete_selections(
        self,
        ids: conlist(int, min_items=1, unique_items=True) = Query(  # pyright: ignore[reportInvalidTypeForm] # noqa: B008
            description="ids of selections to delete", alias="id"
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.boot_source_selections.delete_many(
            query=QuerySpec(
                where=BootSourceSelectionClauseFactory.with_ids(ids)
            )
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/selection_statuses",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageStatusListResponse,
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_selection_status(
        self,
        filters: BootSourceSelectionStatusFilterParams = Depends(),  # noqa: B008
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatusListResponse:
        statuses = await services.boot_source_selection_status.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(where=filters.to_clause()),
        )

        next_link = None
        if statuses.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/selection_statuses?"
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
        path="/selection_statuses/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ImageStatusResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_selection_status(
        self,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatusResponse:
        status = await services.boot_source_selection_status.get_by_id(id)

        if not status:
            raise NotFoundException()

        return ImageStatusResponse.from_model(status)

    @handler(
        path="/selection_statistics",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ImageStatisticListResponse,
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_selection_statistic(
        self,
        filters: BootSourceSelectionStatisticFilterParams = Depends(),  # noqa: B008
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatisticListResponse:
        statistics = (
            await services.boot_source_selections.list_selections_statistics(
                page=pagination_params.page,
                size=pagination_params.size,
                query=QuerySpec(where=filters.to_clause()),
            )
        )

        next_link = None
        if statistics.has_next(pagination_params.page, pagination_params.size):
            next_link = (
                f"{V3_API_PREFIX}/selection_statistics?"
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
        path="/selection_statistics/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ImageStatisticResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_selection_statistic(
        self,
        id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> ImageStatisticResponse:
        statistic = await services.boot_source_selections.get_selection_statistic_by_id(
            id
        )

        if not statistic:
            raise NotFoundException()

        return ImageStatisticResponse.from_model(statistic)
