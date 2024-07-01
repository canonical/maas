# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.query import TokenPaginationParams
from maasapiserver.v3.api.models.responses.subnets import SubnetsListResponse
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


class SubnetsHandler(Handler):
    """Subnets API handler."""

    TAGS = ["Subnets"]

    @handler(
        path="/subnets",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": SubnetsListResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_subnets(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        subnets = await services.subnets.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
        )
        return SubnetsListResponse(
            items=[
                subnet.to_response(f"{V3_API_PREFIX}/subnets")
                for subnet in subnets.items
            ],
            next=f"{V3_API_PREFIX}/subnets?"
            f"{TokenPaginationParams.to_href_format(subnets.next_token, token_pagination_params.size)}"
            if subnets.next_token
            else None,
        )
