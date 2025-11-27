# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Depends, Header, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadGatewayErrorBodyResponse,
    ConflictBodyResponse,
    NotFoundBodyResponse,
    UnauthorizedBodyResponse,
)
from maasapiserver.common.utils.http import extract_absolute_uri
from maasapiserver.v3.api import cookie_manager, services
from maasapiserver.v3.api.public.models.requests.external_auth import (
    OAuthProviderRequest,
)
from maasapiserver.v3.api.public.models.requests.query import PaginationParams
from maasapiserver.v3.api.public.models.responses.oauth2 import (
    AccessTokenResponse,
    AuthProviderInfoResponse,
    OAuthProviderResponse,
    OAuthProvidersListResponse,
)
from maasapiserver.v3.auth.base import (
    check_permissions,
    get_authenticated_user,
)
from maasapiserver.v3.auth.cookie_manager import (
    EncryptedCookieManager,
    MAASOAuth2Cookie,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.jwt import UserRole
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
)
from maasservicelayer.models.auth import AuthenticatedUser
from maasservicelayer.services import ServiceCollectionV3


class AuthHandler(Handler):
    """Auth API handler."""

    TAGS = ["Auth"]

    TOKEN_TYPE = "bearer"

    @handler(
        path="/auth/login",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": AccessTokenResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
    )
    async def login(
        self,
        request: Request,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        form_data: OAuth2PasswordRequestForm = Depends(),  # noqa: B008
    ) -> AccessTokenResponse:
        if (
            external_auth_info
            := await request.state.services.external_auth.get_external_auth()
        ):
            await request.state.services.external_auth.raise_discharge_required_exception(
                external_auth_info,
                extract_absolute_uri(request),
                request.headers,
            )
        token = await services.auth.login(
            form_data.username, form_data.password
        )
        return AccessTokenResponse(
            token_type=self.TOKEN_TYPE, access_token=token.encoded
        )

    @handler(
        path="/auth/access_token",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": AccessTokenResponse,
            },
            401: {"model": UnauthorizedBodyResponse},
        },
        response_model_exclude_none=True,
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.USER}))
        ],
    )
    async def get_access_token(
        self,
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> AccessTokenResponse:
        assert authenticated_user is not None
        token = await services.auth.access_token(authenticated_user)
        return AccessTokenResponse(
            token_type=self.TOKEN_TYPE, access_token=token.encoded
        )

    @handler(
        path="/auth/oauth/authorization_url",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": AuthProviderInfoResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=200,
    )
    async def initiate_oauth_flow(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        cookie_manager: EncryptedCookieManager = Depends(cookie_manager),  # noqa: B008
    ):
        """Initiate the OAuth flow by generating the authorization URL and setting the necessary security cookies."""
        client = await services.external_oauth.get_client()
        if not client:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                        message="No external OAuth provider is configured.",
                    )
                ]
            )
        data = client.generate_authorization_url()
        cookie_manager.set_auth_cookie(
            value=data.state, key=MAASOAuth2Cookie.AUTH_STATE
        )
        cookie_manager.set_auth_cookie(
            value=data.nonce, key=MAASOAuth2Cookie.AUTH_NONCE
        )
        return AuthProviderInfoResponse(
            auth_url=data.authorization_url,
            provider_name=client.get_provider_name(),
        )

    @handler(
        path="/auth/oauth/providers/{provider_id}",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": OAuthProviderResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def get_oauth_provider_by_id(
        self,
        provider_id: int,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> OAuthProviderResponse:
        if provider := await services.external_oauth.get_by_id(id=provider_id):
            user_count = await services.users.count_by_provider(
                provider_id=provider.id
            )
            return OAuthProviderResponse.from_model(
                provider=provider, user_count=user_count
            )

        raise NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                    message="No OIDC provider with the given ID was found.",
                )
            ]
        )

    @handler(
        path="/auth/oauth/providers",
        methods=["GET"],
        tags=TAGS,
        responses={200: {"model": OAuthProvidersListResponse}},
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def list_oauth_providers(
        self,
        pagination_params: PaginationParams = Depends(),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ):
        providers = await services.external_oauth.list(
            page=pagination_params.page, size=pagination_params.size
        )
        next_link = None
        if providers.has_next(pagination_params.page, pagination_params.size):
            next_link = f"{V3_API_PREFIX}/auth/oauth/providers?{pagination_params.to_next_href_format()}"
        return OAuthProvidersListResponse(
            items=[
                OAuthProviderResponse.from_model(provider)
                for provider in providers.items
            ],
            total=providers.total,
            next=next_link,
        )

    @handler(
        path="/auth/oauth/providers/{provider_id}",
        methods=["PUT"],
        tags=TAGS,
        responses={
            200: {"model": OAuthProviderResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def update_oauth_provider(
        self,
        provider_id: int,
        request: OAuthProviderRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> OAuthProviderResponse:
        builder = request.to_builder()
        if updated_provider := await services.external_oauth.update_provider(
            id=provider_id,
            builder=builder,
        ):
            return OAuthProviderResponse.from_model(updated_provider)

        raise NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                    message="No OIDC provider with the given ID was found.",
                )
            ]
        )

    @handler(
        path="/auth/oauth:is_active",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": OAuthProviderResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=200,
        dependencies=[
            Depends(
                check_permissions(
                    required_roles={UserRole.ADMIN},
                )
            )
        ],
    )
    async def get_oauth_provider(
        self,
        response: Response,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> OAuthProviderResponse:
        if provider := await services.external_oauth.get_provider():
            user_count = await services.users.count_by_provider(
                provider_id=provider.id
            )
            response.headers["ETag"] = provider.etag()
            return OAuthProviderResponse.from_model(
                provider=provider,
                user_count=user_count,
            )
        raise NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
                    message="No external OAuth provider is configured.",
                )
            ]
        )

    @handler(
        path="/auth/oauth/providers",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {"model": OAuthProviderResponse},
            409: {"model": ConflictBodyResponse},
            502: {"model": BadGatewayErrorBodyResponse},
        },
        status_code=200,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def create_oauth_provider(
        self,
        request: OAuthProviderRequest,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> OAuthProviderResponse:
        builder = request.to_builder()
        provider = await services.external_oauth.create(builder)
        return OAuthProviderResponse.from_model(provider=provider)

    @handler(
        path="/auth/oauth/providers/{provider_id}",
        methods=["DELETE"],
        tags=TAGS,
        responses={
            200: {"model": OAuthProviderResponse},
            404: {"model": NotFoundBodyResponse},
        },
        status_code=204,
        dependencies=[
            Depends(check_permissions(required_roles={UserRole.ADMIN}))
        ],
    )
    async def delete_oauth_provider(
        self,
        provider_id: int,
        etag_if_match: str | None = Header(alias="if-match", default=None),
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> Response:
        await services.external_oauth.delete_by_id(provider_id, etag_if_match)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
