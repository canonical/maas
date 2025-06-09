# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from fastapi import Depends, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.discoveries import (
    DiscoveriesIPAndMacFiltersParams,
)
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
from maasservicelayer.exceptions.catalog import NotFoundException
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
    ) -> DiscoveriesListResponse:
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
    ) -> DiscoveryResponse:
        discovery = await services.discoveries.get_by_id(discovery_id)
        if not discovery:
            raise NotFoundException()

        response.headers["ETag"] = discovery.etag()
        return DiscoveryResponse.from_model(
            discovery=discovery,
            self_base_hyperlink=f"{V3_API_PREFIX}/discoveries",
        )

    @handler(
        path="/discoveries",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def clear_all_discoveries_with_optional_ip_and_mac(
        self,
        ip_and_mac: DiscoveriesIPAndMacFiltersParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        if ip_and_mac.ip is not None and ip_and_mac.mac is not None:
            await services.discoveries.clear_by_ip_and_mac(
                ip=ip_and_mac.ip,  # pyright: ignore [reportArgumentType]
                mac=ip_and_mac.mac,
            )
        else:
            await services.discoveries.clear_all()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/discoveries:clear_neighbours",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def clear_neighbours_discoveries(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.discoveries.clear_neighbours()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/discoveries:clear_dns",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
        },
        response_model_exclude_none=True,
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def clear_rdns_and_mdns_discoveries(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.discoveries.clear_mdns_and_rdns_records()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
