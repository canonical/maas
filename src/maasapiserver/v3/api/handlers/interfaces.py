from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.models.requests.query import TokenPaginationParams
from maasapiserver.v3.api.models.responses.interfaces import (
    InterfaceListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3


class InterfacesHandler(Handler):
    """Interface API handler."""

    TAGS = ["Machine"]

    @handler(
        path="/machines/{node_id}/interfaces",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": InterfaceListResponse,
            },
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_interfaces(
        self,
        node_id: int,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        interfaces = await services.interfaces.list(
            node_id=node_id,
            token=token_pagination_params.token,
            size=token_pagination_params.size,
        )
        return InterfaceListResponse(
            items=[
                interface.to_response(
                    f"{V3_API_PREFIX}/machines/{node_id}/interfaces"
                )
                for interface in interfaces.items
            ],
            next=f"{V3_API_PREFIX}/machines/{node_id}/interfaces?"
            f"{TokenPaginationParams.to_href_format(interfaces.next_token, token_pagination_params.size)}"
            if interfaces.next_token
            else None,
        )
