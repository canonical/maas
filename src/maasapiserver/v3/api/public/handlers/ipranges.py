# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

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
from maasapiserver.v3.api.public.models.responses.ipranges import (
    IPRangeListResponse,
    IPRangeResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.services import ServiceCollectionV3


class IPRangesHandler(Handler):
    """IPRanges API handler."""

    TAGS = ["IPRanges"]

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": IPRangeListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        ipranges = await services.ipranges.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                        IPRangeClauseFactory.with_vlan_id(vlan_id),
                        IPRangeClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            ),
        )
        return IPRangeListResponse(
            items=[
                IPRangeResponse.from_model(
                    iprange=iprange,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/",
                )
                for iprange in ipranges.items
            ],
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges?"
                f"{TokenPaginationParams.to_href_format(ipranges.next_token, token_pagination_params.size)}"
                if ipranges.next_token
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/{id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": IPRangeResponse,
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
    async def get_fabric_vlan_subnet_iprange(
        self,
        fabric_id: int,
        vlan_id: int,
        subnet_id: int,
        id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        iprange = await services.ipranges.get_one(
            QuerySpec(
                where=IPRangeClauseFactory.and_clauses(
                    [
                        IPRangeClauseFactory.with_id(id),
                        IPRangeClauseFactory.with_subnet_id(subnet_id),
                        IPRangeClauseFactory.with_vlan_id(vlan_id),
                        IPRangeClauseFactory.with_fabric_id(fabric_id),
                    ]
                )
            )
        )
        if not iprange:
            return NotFoundResponse()

        response.headers["ETag"] = iprange.etag()
        return IPRangeResponse.from_model(
            iprange=iprange,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans/{vlan_id}/subnets/{subnet_id}/ipranges/",
        )
