# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.query import TokenPaginationParams
from maasapiserver.v3.api.models.responses.vlans import VlansListResponse
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


class VlansHandler(Handler):
    """Vlans API handler."""

    TAGS = ["Vlans"]

    @handler(
        path="/vlans",
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
    async def list_vlans(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        vlans = await services.vlans.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
        )
        return VlansListResponse(
            items=[
                vlan.to_response(f"{V3_API_PREFIX}/vlans")
                for vlan in vlans.items
            ],
            next=f"{V3_API_PREFIX}/vlans?"
            f"{TokenPaginationParams.to_href_format(vlans.next_token, token_pagination_params.size)}"
            if vlans.next_token
            else None,
        )
