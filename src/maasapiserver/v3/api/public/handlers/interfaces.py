# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Response

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.interfaces import (
    InterfaceListResponse,
    InterfaceResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.services import ServiceCollectionV3


class InterfacesHandler(Handler):
    """Interface API handler."""

    TAGS = ["Interfaces"]

    @handler(
        path="/machines/{node_id}/interfaces",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": InterfaceListResponse,
            },
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
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        interfaces = await services.interfaces.list_for_node(
            node_id=node_id,
            page=pagination_params.page,
            size=pagination_params.size,
        )
        return InterfaceListResponse(
            items=[
                InterfaceResponse.from_model(
                    interface=interface,
                    self_base_hyperlink=f"{V3_API_PREFIX}/machines/{node_id}/interfaces",
                )
                for interface in interfaces.items
            ],
            total=interfaces.total,
            next=(
                f"{V3_API_PREFIX}/machines/{node_id}/interfaces?"
                f"{pagination_params.to_next_href_format()}"
                if interfaces.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )
