#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.reservedips import (
    ReservedIPCreateRequest,
    ReservedIPUpdateRequest,
)
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.reservedips import (
    ReservedIPResponse,
    ReservedIPsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
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


class ReservedIPsHandler(Handler):
    """Reserved IPs API handler."""

    TAGS = ["ReservedIP"]

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ReservedIPsListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=200,
        response_model_exclude_none=True,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.USER},
                )
            )
        ],
    )
    async def list_fabric_vlan_subnet_reserved_ips(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        pagination_params: PaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> ReservedIPsListResponse:
        query = QuerySpec(
            where=ReservedIPsClauseFactory.and_clauses(
                [
                    ReservedIPsClauseFactory.with_fabric_id(fabric_id),
                    ReservedIPsClauseFactory.with_subnet_id(subnet_id),
                    ReservedIPsClauseFactory.with_vlan_id(vlan_id),
                ]
            )
        )
        reservedips = await services.reservedips.list(
            page=pagination_params.page,
            size=pagination_params.size,
            query=query,
        )
        return ReservedIPsListResponse(
            items=[
                ReservedIPResponse.from_model(
                    reservedip=reservedip,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
                )
                for reservedip in reservedips.items
            ],
            total=reservedips.total,
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips?"
                f"{pagination_params.to_next_href_format()}"
                if reservedips.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips/{reservedip_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": ReservedIPResponse,
                "headers": {
                    "ETag": OPENAPI_ETAG_HEADER,
                },
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_fabric_vlan_subnet_reserved_ip(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        reservedip_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        reservedip = await services.reservedips.get_one(
            query=QuerySpec(
                ReservedIPsClauseFactory.and_clauses(
                    [
                        ReservedIPsClauseFactory.with_id(reservedip_id),
                        ReservedIPsClauseFactory.with_fabric_id(fabric_id),
                        ReservedIPsClauseFactory.with_subnet_id(subnet_id),
                        ReservedIPsClauseFactory.with_vlan_id(vlan_id),
                    ]
                )
            )
        )

        if not reservedip:
            return NotFoundResponse()

        response.headers["ETag"] = reservedip.etag()
        return ReservedIPResponse.from_model(
            reservedip=reservedip,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": ReservedIPResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_fabric_vlan_subnet_reserved_ip(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        reservedip_request: ReservedIPCreateRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        subnet = await services.subnets.get_one(
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
        if not subnet:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Could not find subnet {subnet_id} in VLAN {vlan_id} in fabric {fabric_id}",
                    )
                ]
            )
        builder = await reservedip_request.to_builder(subnet, services)
        reservedip = await services.reservedips.create(builder)

        response.headers["ETag"] = reservedip.etag()
        return ReservedIPResponse.from_model(
            reservedip=reservedip,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips/{id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": ReservedIPResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_fabric_vlan_subnet_reserved_ip(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        reservedip_request: ReservedIPUpdateRequest,
        response: Response,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        query = QuerySpec(
            where=ReservedIPsClauseFactory.and_clauses(
                [
                    ReservedIPsClauseFactory.with_id(id),
                    ReservedIPsClauseFactory.with_subnet_id(subnet_id),
                    ReservedIPsClauseFactory.with_vlan_id(vlan_id),
                    ReservedIPsClauseFactory.with_fabric_id(fabric_id),
                ]
            )
        )
        existing_reservedip = await services.reservedips.get_one(query=query)
        if not existing_reservedip:
            return NotFoundResponse()

        builder = reservedip_request.to_builder(existing_reservedip)
        reservedip = await services.reservedips.update_one(
            query=query, builder=builder, etag_if_match=etag_if_match
        )

        response.headers["ETag"] = reservedip.etag()
        return ReservedIPResponse.from_model(
            reservedip=reservedip,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips/{id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_fabric_vlan_subnet_reserved_ip(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        query = QuerySpec(
            where=ReservedIPsClauseFactory.and_clauses(
                [
                    ReservedIPsClauseFactory.with_id(id),
                    ReservedIPsClauseFactory.with_subnet_id(subnet_id),
                    ReservedIPsClauseFactory.with_vlan_id(vlan_id),
                    ReservedIPsClauseFactory.with_fabric_id(fabric_id),
                ]
            )
        )
        await services.reservedips.delete_one(
            query=query, etag_if_match=etag_if_match
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)
