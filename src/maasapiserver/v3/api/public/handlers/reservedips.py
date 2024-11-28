#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
    NotFoundResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.reservedips import (
    ReservedIPResponse,
    ReservedIPsListResponse,
)
from maasapiserver.v3.api.public.models.responses.resource_pools import (
    ResourcePoolsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
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
                "model": ResourcePoolsListResponse,
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
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
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
            token=token_pagination_params.token,
            size=token_pagination_params.size,
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
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/reserved_ips?"
                f"{TokenPaginationParams.to_href_format(reservedips.next_token, token_pagination_params.size)}"
                if reservedips.next_token
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
                    "ETag": {"description": "The ETag for the resource"}
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
