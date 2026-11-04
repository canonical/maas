#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Annotated

from fastapi import Depends, Response, status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ForbiddenBodyResponse,
    NotFoundBodyResponse,
    UnauthorizedBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.api_tokens import (
    AdminApiTokenFiltersParams,
    ApiTokenCreateRequest,
    ApiTokenFiltersParams,
    combine_clauses,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.api_tokens import (
    ApiTokenCreatedResponse,
    ApiTokenResponse,
    ApiTokensListResponse,
)
from maasapiserver.v3.auth.base import check_authentication, check_permissions
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.openfga.base import MAASResourceEntitlement
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.api_tokens import (
    ApiTokenClauseFactory,
    ApiTokenOrderByClauses,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.models.tokens import ApiToken
from maasservicelayer.services import ServiceCollectionV3

ME_BASE = f"{V3_API_PREFIX}/users/me/pats"
ADMIN_BASE = f"{V3_API_PREFIX}/pats"


async def _get_my_token_or_404(
    services: ServiceCollectionV3, token_id: int, user_id: int
) -> ApiToken:
    token = await services.api_tokens.get_one(
        QuerySpec(
            where=ApiTokenClauseFactory.and_clauses(
                [
                    ApiTokenClauseFactory.with_id(token_id),
                    ApiTokenClauseFactory.with_user_id(user_id),
                ]
            )
        )
    )
    if token is None:
        raise NotFoundException()
    return token


# There is a minor duplication here for safety purposes:
# one should be used by admin look ups, the other for personal
# look ups.
async def _get_any_token_or_404(
    services: ServiceCollectionV3, token_id: int
) -> ApiToken:
    token = await services.api_tokens.get_one(
        QuerySpec(where=ApiTokenClauseFactory.with_id(token_id))
    )
    if token is None:
        raise NotFoundException()
    return token


async def _list_tokens(
    services: ServiceCollectionV3,
    pagination_params: PaginationParams,
    filters: ApiTokenFiltersParams,
    extra_clauses: list,
    base_href: str,
) -> ApiTokensListResponse:
    tokens = await services.api_tokens.list(
        page=pagination_params.page,
        size=pagination_params.size,
        query=QuerySpec(
            where=combine_clauses(filters.to_clauses() + extra_clauses),
            order_by=ApiTokenOrderByClauses.last_used_at_desc(),
        ),
    )
    next_link = None
    if tokens.has_next(pagination_params.page, pagination_params.size):
        next_link = f"{base_href}?{pagination_params.to_next_href_format()}"
        if query_filters := filters.to_href_format():
            next_link += f"&{query_filters}"
    return ApiTokensListResponse(
        items=[
            ApiTokenResponse.from_model(token, base_href)
            for token in tokens.items
        ],
        total=tokens.total,
        next=next_link,
    )


class ApiTokensHandler(Handler):
    """Personal access tokens API handler."""

    TAGS = ["ApiTokens"]

    @handler(
        path="/users/me/pats",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ApiTokensListResponse},
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[Depends(check_authentication())],
    )
    async def list_my_tokens(
        self,
        pagination_params: Annotated[PaginationParams, Depends()],
        filters: Annotated[ApiTokenFiltersParams, Depends()],
        authenticated_user: Annotated[
            AuthenticatedUser, Depends(check_authentication())
        ],
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> ApiTokensListResponse:
        return await _list_tokens(
            services,
            pagination_params,
            filters,
            [ApiTokenClauseFactory.with_user_id(authenticated_user.id)],
            ME_BASE,
        )

    @handler(
        path="/users/me/pats/{token_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ApiTokenResponse},
            401: {"model": UnauthorizedBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[Depends(check_authentication())],
    )
    async def get_my_token(
        self,
        token_id: int,
        authenticated_user: Annotated[
            AuthenticatedUser, Depends(check_authentication())
        ],
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> ApiTokenResponse:
        token = await _get_my_token_or_404(
            services, token_id, authenticated_user.id
        )
        return ApiTokenResponse.from_model(token, ME_BASE)

    @handler(
        path="/users/me/pats",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {"model": ApiTokenCreatedResponse},
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=201,
        dependencies=[Depends(check_authentication())],
    )
    async def create_my_token(
        self,
        request: ApiTokenCreateRequest,
        authenticated_user: Annotated[
            AuthenticatedUser, Depends(check_authentication())
        ],
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> ApiTokenCreatedResponse:
        token, raw_token = await services.api_tokens.create_token(
            user_id=authenticated_user.id,
            name=request.name,
            expires_at=request.expires_at,
        )
        return ApiTokenCreatedResponse.from_model(
            token, ME_BASE, token=raw_token
        )

    @handler(
        path="/users/me/pats/{token_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            401: {"model": UnauthorizedBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[Depends(check_authentication())],
    )
    async def revoke_my_token(
        self,
        token_id: int,
        authenticated_user: Annotated[
            AuthenticatedUser, Depends(check_authentication())
        ],
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> Response:
        token = await _get_my_token_or_404(
            services, token_id, authenticated_user.id
        )
        await services.api_tokens.revoke(token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/pats",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ApiTokensListResponse},
            401: {"model": UnauthorizedBodyResponse},
            403: {"model": ForbiddenBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES
                )
            )
        ],
    )
    async def list_tokens(
        self,
        pagination_params: Annotated[PaginationParams, Depends()],
        filters: Annotated[AdminApiTokenFiltersParams, Depends()],
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> ApiTokensListResponse:
        return await _list_tokens(
            services, pagination_params, filters, [], ADMIN_BASE
        )

    @handler(
        path="/pats/{token_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": ApiTokenResponse},
            401: {"model": UnauthorizedBodyResponse},
            403: {"model": ForbiddenBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_VIEW_IDENTITIES
                )
            )
        ],
    )
    async def get_token(
        self,
        token_id: int,
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> ApiTokenResponse:
        token = await _get_any_token_or_404(services, token_id)
        return ApiTokenResponse.from_model(token, ADMIN_BASE)

    @handler(
        path="/pats/{token_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            401: {"model": UnauthorizedBodyResponse},
            403: {"model": ForbiddenBodyResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(
                check_permissions(
                    openfga_permission=MAASResourceEntitlement.CAN_EDIT_IDENTITIES
                )
            )
        ],
    )
    async def revoke_token(
        self,
        token_id: int,
        services: Annotated[ServiceCollectionV3, Depends(services)],
    ) -> Response:
        token = await _get_any_token_or_404(services, token_id)
        await services.api_tokens.revoke(token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
