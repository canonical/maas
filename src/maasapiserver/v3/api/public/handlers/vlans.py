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
from maasapiserver.v3.api.public.models.requests.vlans import VlanCreateRequest
from maasapiserver.v3.api.public.models.responses.vlans import (
    VlanResponse,
    VlansListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.vlans import VlansClauseFactory
from maasservicelayer.services import ServiceCollectionV3


class VlansHandler(Handler):
    """Vlans API handler."""

    TAGS = ["Vlans"]

    @handler(
        path="/fabrics/{fabric_id}/vlans",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": VlanResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_fabric_vlan(
        self,
        fabric_id: int,
        vlan_request: VlanCreateRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        vlan_builder = vlan_request.to_builder()
        vlan_builder.with_fabric_id(fabric_id)
        vlan = await services.vlans.create(resource=vlan_builder.build())
        response.headers["ETag"] = vlan.etag()
        return VlanResponse.from_model(
            vlan=vlan,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans",
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": VlansListResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_fabric_vlans(
        self,
        fabric_id: int,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        vlans = await services.vlans.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=QuerySpec(
                where=VlansClauseFactory.with_fabric_id(fabric_id)
            ),
        )
        return VlansListResponse(
            items=[
                VlanResponse.from_model(
                    vlan=vlan,
                    self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans",
                )
                for vlan in vlans.items
            ],
            next=(
                f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans?"
                f"{TokenPaginationParams.to_href_format(vlans.next_token, token_pagination_params.size)}"
                if vlans.next_token
                else None
            ),
        )

    @handler(
        path="/fabrics/{fabric_id}/vlans/{vlan_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": VlanResponse,
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
    async def get_fabric_vlan(
        self,
        fabric_id: int,
        vlan_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        vlan = await services.vlans.get_by_id(
            fabric_id=fabric_id, vlan_id=vlan_id
        )
        if not vlan:
            return NotFoundResponse()

        response.headers["ETag"] = vlan.etag()
        return VlanResponse.from_model(
            vlan=vlan,
            self_base_hyperlink=f"{V3_API_PREFIX}/fabrics/{fabric_id}/vlans",
        )
