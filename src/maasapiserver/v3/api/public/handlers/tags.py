# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    NotFoundBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.requests.tags import TagRequest
from maasapiserver.v3.api.public.models.responses.base import (
    OPENAPI_ETAG_HEADER,
)
from maasapiserver.v3.api.public.models.responses.tags import (
    TagResponse,
    TagsListResponse,
)
from maasapiserver.v3.auth.base import check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.services import ServiceCollectionV3


class TagsHandler(Handler):
    """Tags API handler."""

    TAGS = ["Tags"]

    @handler(
        path="/tags",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": TagsListResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def list_tags(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> TagsListResponse:
        tags = await services.tags.list(
            page=pagination_params.page, size=pagination_params.size
        )
        return TagsListResponse(
            items=[
                TagResponse.from_model(
                    tag=tag, self_base_hyperlink=f"{V3_API_PREFIX}/tags"
                )
                for tag in tags.items
            ],
            total=tags.total,
            next=(
                f"{V3_API_PREFIX}/tags?"
                f"{pagination_params.to_next_href_format()}"
                if tags.has_next(
                    pagination_params.page, pagination_params.size
                )
                else None
            ),
        )

    @handler(
        path="/tags/{tag_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": TagResponse,
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
    async def get_tag(
        self,
        tag_id: int,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> TagResponse:
        tag = await services.tags.get_by_id(tag_id)
        if tag is None:
            raise NotFoundException()
        response.headers["ETag"] = tag.etag()
        return TagResponse.from_model(
            tag=tag, self_base_hyperlink=f"{V3_API_PREFIX}/tags"
        )

    @handler(
        path="/tags",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": TagResponse,
                "headers": {"ETag": OPENAPI_ETAG_HEADER},
            },
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_tag(
        self,
        tag_request: TagRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> TagResponse:
        builder = tag_request.to_builder()
        tag = await services.tags.create(builder)
        response.headers["ETag"] = tag.etag()
        return TagResponse.from_model(
            tag=tag, self_base_hyperlink=f"{V3_API_PREFIX}/tags"
        )

    @handler(
        path="/tags/{tag_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {
                "model": TagResponse,
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
    async def update_tag(
        self,
        tag_id: int,
        tag_request: TagRequest,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> TagResponse:
        builder = tag_request.to_builder()
        tag = await services.tags.update_by_id(tag_id, builder)
        response.headers["ETag"] = tag.etag()
        return TagResponse.from_model(
            tag=tag, self_base_hyperlink=f"{V3_API_PREFIX}/tags"
        )

    @handler(
        path="/tags/{tag_id}",
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
    async def delete_tag(
        self,
        tag_id: int,
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.tags.delete_by_id(tag_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
