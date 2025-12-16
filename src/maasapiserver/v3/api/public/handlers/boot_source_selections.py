# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.boot_source_selections import (
    BootSourceSelectionFilterParams,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.boot_images_common import (
    ImageStatusListResponse,
    ImageStatusResponse,
)
from maasapiserver.v3.api.public.models.responses.boot_source_selections import (
    BootSourceSelectionListResponse,
    BootSourceSelectionResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
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
            200: {"model": BootSourceSelectionListResponse},
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
    ) -> BootSourceSelectionListResponse:
        boot_source_selections = await services.boot_source_selections.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )

        return BootSourceSelectionListResponse(
            items=[
                BootSourceSelectionResponse.from_model(
                    boot_source_selection=boot_source_selection,
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
            200: {"model": BootSourceSelectionResponse},
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
    ) -> BootSourceSelectionResponse:
        boot_source_selection = (
            await services.boot_source_selections.get_by_id(id)
        )
        if not boot_source_selection:
            raise NotFoundException()
        return BootSourceSelectionResponse.from_model(
            boot_source_selection=boot_source_selection,
            self_base_hyperlink=f"{V3_API_PREFIX}/selections/{id}",
        )

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
        filters: BootSourceSelectionFilterParams = Depends(),  # noqa: B008
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
