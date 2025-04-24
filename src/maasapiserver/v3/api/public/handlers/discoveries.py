# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.discoveries import (
    DiscoveriesListResponse,
    DiscoveryResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


class DiscoveriesHandler(Handler):
    """Discoveries API handler."""

    TAGS = ["Discoveries"]

    @handler(
        path="/discoveries",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": DiscoveriesListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_discoveries(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        # TODO: order by last seen
        discoveries = await services.discoveries.list(
            page=pagination_params.page,
            size=pagination_params.size,
        )
        next_link = None
        if discoveries.has_next(
            pagination_params.page, pagination_params.size
        ):
            next_link = f"{V3_API_PREFIX}/discoveries?{pagination_params.to_next_href_format()}"
        return DiscoveriesListResponse(
            items=[
                DiscoveryResponse.from_model(
                    discovery=discovery,
                    self_base_hyperlink=f"{V3_API_PREFIX}/discoveries",
                )
                for discovery in discoveries.items
            ],
            total=discoveries.total,
            next=next_link,
        )

    @handler(
        path="/discoveries/{discovery_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": DiscoveryResponse,
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
    async def get_discovery(
        self,
        discovery_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        discovery = await services.discoveries.get_by_id(discovery_id)
        if not discovery:
            return NotFoundResponse()

        response.headers["ETag"] = discovery.etag()
        return DiscoveryResponse.from_model(
            discovery=discovery,
            self_base_hyperlink=f"{V3_API_PREFIX}/discoveries",
        )
