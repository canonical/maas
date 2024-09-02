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
from maasapiserver.v3.api.public.models.responses.spaces import (
    SpaceResponse,
    SpacesListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasapiserver.v3.services import ServiceCollectionV3
from maasservicelayer.auth.jwt import UserRole


class SpacesHandler(Handler):
    """Spaces API handler."""

    TAGS = ["Spaces"]

    @handler(
        path="/spaces",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": SpacesListResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_spaces(
        self,
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        spaces = await services.spaces.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
        )
        return SpacesListResponse(
            items=[
                SpaceResponse.from_model(
                    space=space, self_base_hyperlink=f"{V3_API_PREFIX}/spaces"
                )
                for space in spaces.items
            ],
            next=(
                f"{V3_API_PREFIX}/spaces?"
                f"{TokenPaginationParams.to_href_format(spaces.next_token, token_pagination_params.size)}"
                if spaces.next_token
                else None
            ),
        )

    @handler(
        path="/spaces/{space_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SpaceResponse,
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
    async def get_space(
        self,
        space_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        space = await services.spaces.get_by_id(space_id)
        if not space:
            return NotFoundResponse()

        response.headers["ETag"] = space.etag()
        return SpaceResponse.from_model(
            space=space, self_base_hyperlink=f"{V3_API_PREFIX}/spaces"
        )
