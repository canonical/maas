# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.staticroutes import (
    StaticRouteRequest,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.staticroutes import (
    StaticRouteResponse,
    StaticRoutesListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesClauseFactory,
)
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.services import ServiceCollectionV3


class StaticRoutesHandler(Handler):
    """Static Routes API handler."""

    TAGS = ["Static Routes"]

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": StaticRoutesListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabric_vlan_subnet_staticroutes(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> StaticRoutesListResponse:
        static_routes = await services.staticroutes.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_source_id(subnet_id),
                        StaticRoutesClauseFactory.with_vlan_id(vlan_id),
                        StaticRoutesClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            ),
        )
        return StaticRoutesListResponse(
            items=[
                StaticRouteResponse.from_model(
                    static_route=static_route,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/",
                )
                for static_route in static_routes.items
            ],
            total=static_routes.total,
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes?"
                f"{pagination_params.to_next_href_format()}"
                if static_routes.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": StaticRouteResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_fabric_vlan_subnet_staticroute(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        staticroute_request: StaticRouteRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> StaticRouteResponse:
        source_subnet = await services.subnets.get_one(
            query=QuerySpec(
                where=SubnetClauseFactory.and_clauses(
                    [
                        SubnetClauseFactory.with_id(subnet_id),
                        SubnetClauseFactory.with_vlan_id(vlan_id),
                        SubnetClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not source_subnet:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find subnet {subnet_id} in VLAN {vlan_id} in fabric {fabric_id}.",
                    )
                ]
            )

        builder = await staticroute_request.to_builder(source_subnet, services)
        static_route = await services.staticroutes.create(builder)

        response.headers["ETag"] = static_route.etag()
        return StaticRouteResponse.from_model(
            static_route=static_route,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": StaticRouteResponse,
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
    async def get_fabric_vlan_subnet_staticroute(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        static_route = await services.staticroutes.get_one(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(id),
                        StaticRoutesClauseFactory.with_source_id(subnet_id),
                        StaticRoutesClauseFactory.with_vlan_id(vlan_id),
                        StaticRoutesClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not static_route:
            return NotFoundResponse()

        response.headers["ETag"] = static_route.etag()
        return StaticRouteResponse.from_model(
            static_route=static_route,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/{id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": StaticRouteResponse,
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
    async def update_fabric_vlan_subnet_staticroute(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        staticroute_request: StaticRouteRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> StaticRouteResponse:
        source_subnet = await services.subnets.get_one(
            query=QuerySpec(
                where=SubnetClauseFactory.and_clauses(
                    [
                        SubnetClauseFactory.with_id(subnet_id),
                        SubnetClauseFactory.with_vlan_id(vlan_id),
                        SubnetClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not source_subnet:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find subnet {subnet_id} in VLAN {vlan_id} in fabric {fabric_id}.",
                    )
                ]
            )
        builder = await staticroute_request.to_builder(source_subnet, services)
        static_route = await services.staticroutes.update_one(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(id),
                        StaticRoutesClauseFactory.with_source_id(
                            source_subnet.id
                        ),
                    ]
                )
            ),
            builder=builder,
        )

        response.headers["ETag"] = static_route.etag()
        return StaticRouteResponse.from_model(
            static_route=static_route,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/staticroutes/{id}",
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
    async def delete_fabric_vlan_subnet_staticroute(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        static_route = await services.staticroutes.get_one(
            query=QuerySpec(
                where=StaticRoutesClauseFactory.and_clauses(
                    [
                        StaticRoutesClauseFactory.with_id(id),
                        StaticRoutesClauseFactory.with_source_id(subnet_id),
                        StaticRoutesClauseFactory.with_vlan_id(vlan_id),
                        StaticRoutesClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if static_route:
            await services.staticroutes.delete_by_id(
                static_route.id, etag_if_match=etag_if_match
            )

        return Response(status_code=status.HTTP_204_NO_CONTENT)
