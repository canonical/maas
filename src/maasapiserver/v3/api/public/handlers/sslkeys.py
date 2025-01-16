#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Union

from fastapi import Depends, Header, Response
from starlette import status

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    ConflictBodyResponse,
    NotFoundBodyResponse,
    NotFoundResponse,
    UnauthorizedBodyResponse,
    ValidationErrorBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.sslkeys import SSLKeyRequest
from maasapiserver.v3.api.public.models.responses.sslkey import (
    SSLKeyListResponse,
    SSLKeyResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sslkeys import SSLKeyClauseFactory
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class SSLKeysHandler(Handler):
    """SSL Key Handler"""

    TAGS = ["SSLKeys"]

    @handler(
        path="/users/me/sslkeys",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SSLKeyListResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_user_sslkeys(
        self,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        token_pagination_params: TokenPaginationParams = Depends(),
        services: ServiceCollectionV3 = Depends(services),
    ) -> SSLKeyListResponse:
        assert authenticated_user is not None

        sslkeys = await services.sslkeys.list(
            token=token_pagination_params.token,
            size=token_pagination_params.size,
            query=QuerySpec(
                where=SSLKeyClauseFactory.with_user_id(authenticated_user.id),
            ),
        )

        return SSLKeyListResponse(
            items=[
                SSLKeyResponse.from_model(
                    sslkey=sslkey,
                )
                for sslkey in sslkeys.items
            ],
            next=(
                f"{V3_API_PREFIX}/users/me/sslkeys?"
                f"{TokenPaginationParams.to_href_format(sslkeys.next_token, token_pagination_params.size)}"
                if sslkeys.next_token
                else None
            ),
        )

    @handler(
        path="/users/me/sslkeys/{sslkey_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": SSLKeyResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            404: {"model": NotFoundBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_user_sslkey(
        self,
        sslkey_id: int,
        response: Response,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> SSLKeyResponse:
        assert authenticated_user is not None

        sslkey = await services.sslkeys.get_one(
            query=QuerySpec(
                where=SSLKeyClauseFactory.and_clauses(
                    [
                        SSLKeyClauseFactory.with_id(sslkey_id),
                        SSLKeyClauseFactory.with_user_id(
                            authenticated_user.id
                        ),
                    ]
                )
            ),
        )
        if not sslkey:
            return NotFoundResponse()

        response.headers["ETag"] = sslkey.etag()
        return SSLKeyResponse.from_model(
            sslkey=sslkey,
        )

    @handler(
        path="/users/me/sslkeys",
        methods=["POST"],
        tags=TAGS,
        responses={
            201: {
                "model": SSLKeyResponse,
                "headers": {
                    "ETag": {"description": "The ETag for the resource"}
                },
            },
            409: {"model": ConflictBodyResponse},
            422: {"model": ValidationErrorBodyResponse},
        },
        status_code=201,
        response_model_exclude_none=True,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def create_user_sslkey(
        self,
        sslkey_request: SSLKeyRequest,
        response: Response,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> SSLKeyResponse:
        assert authenticated_user is not None

        new_sslkey = await services.sslkeys.create(
            sslkey_request.to_builder()
            .with_user_id(authenticated_user.id)
            .build()
        )

        response.headers["ETag"] = new_sslkey.etag()
        return SSLKeyResponse.from_model(sslkey=new_sslkey)

    @handler(
        path="/users/me/sslkeys/{sslkey_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            204: {},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def delete_user_sslkey(
        self,
        sslkey_id: int,
        authenticated_user: AuthenticatedUser | None = Depends(
            get_authenticated_user
        ),
        etag_if_match: Union[str, None] = Header(
            alias="if-match", default=None
        ),
        services: ServiceCollectionV3 = Depends(services),
    ) -> Response:
        assert authenticated_user is not None

        await services.sslkeys.delete_one(
            query=QuerySpec(
                where=SSLKeyClauseFactory.and_clauses(
                    [
                        SSLKeyClauseFactory.with_id(sslkey_id),
                        SSLKeyClauseFactory.with_user_id(
                            authenticated_user.id
                        ),
                    ]
                )
            ),
            etag_if_match=etag_if_match,
        )

        return Response(status_code=status.HTTP_204_NO_CONTENT)
