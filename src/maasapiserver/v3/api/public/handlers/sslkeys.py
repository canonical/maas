#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    UnauthorizedBodyResponse,
)
from maasapiserver.v3.api import services
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
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
