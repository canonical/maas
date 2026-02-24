# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import secrets

from fastapi import Depends, Header, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from maasapiserver.common.api.base import Handler, handler
from maasapiserver.common.api.models.responses.errors import (
    BadGatewayErrorBodyResponse,
    BadRequestBodyResponse,
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
    AuthInfoResponse,
    CallbackTargetResponse,
    OAuthProviderResponse,
    OAuthProvidersListResponse,
    PreLoginInfoResponse,
    TokenResponse,
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
    BadRequestException,
    BaseExceptionDetail,
    NotFoundException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    INVALID_TOKEN_VIOLATION_TYPE,
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
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": PreLoginInfoResponse,
            },
        },
        response_model_exclude_none=True,
        status_code=200,
    )
    async def pre_login(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
    ) -> PreLoginInfoResponse:
        is_authenticated = authenticated_user is not None
        users_exist = await services.users.has_users()
        return PreLoginInfoResponse(
            is_authenticated=is_authenticated,
            no_users=not users_exist,
        )

    @handler(
        path="/auth/login",
        methods=["POST"],
        tags=TAGS,
        responses={
            200: {
                "model": TokenResponse,
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
    ) -> TokenResponse:
        if (
            external_auth_info
            := await request.state.services.external_auth.get_external_auth()
        ):
            await request.state.services.external_auth.raise_discharge_required_exception(
                external_auth_info,
                extract_absolute_uri(request),
                request.headers,
            )
        tokens = await services.auth.login(
            form_data.username, form_data.password
        )
        return TokenResponse(
            token_type=self.TOKEN_TYPE,
            access_token=tokens.access_token.encoded,
            refresh_token=tokens.refresh_token,
        )

    @handler(
        path="/auth/access_token",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {
                "model": TokenResponse,
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
    ) -> TokenResponse:
        assert authenticated_user is not None
        token = await services.auth.access_token(authenticated_user)
        return TokenResponse(
            token_type=self.TOKEN_TYPE, access_token=token.encoded
        )

    @handler(
        path="/auth/login_info",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": AuthInfoResponse},
            409: {"model": ConflictBodyResponse},
        },
        status_code=200,
    )
    async def initiate_auth_flow(
        self,
        email: str,
        redirect_target: str | None = None,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        cookie_manager: EncryptedCookieManager = Depends(cookie_manager),  # noqa: B008
    ) -> AuthInfoResponse:
        """Initiate the OAuth flow by generating the authorization URL and setting the necessary security cookies,
        if the user is an OIDC user."""
        is_oidc_user = await services.users.is_oidc_user(email)
        if not is_oidc_user:
            return AuthInfoResponse(
                is_oidc=False,
            )
        client = await services.external_oauth.get_client()
        data = client.generate_authorization_url(
            redirect_target=redirect_target or "/"
        )
        cookie_manager.set_auth_cookie(
            value=data.state, key=MAASOAuth2Cookie.AUTH_STATE
        )
        cookie_manager.set_auth_cookie(
            value=data.nonce, key=MAASOAuth2Cookie.AUTH_NONCE
        )
        return AuthInfoResponse(
            auth_url=data.authorization_url,
            provider_name=client.get_provider_name(),
            is_oidc=True,
        )

    @handler(
        path="/auth/oauth/callback",
        methods=["GET"],
        tags=TAGS,
        responses={
            200: {"model": CallbackTargetResponse},
            401: {"model": UnauthorizedBodyResponse},
        },
        status_code=200,
    )
    async def handle_oauth_callback(
        self,
        code: str,
        state: str,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        cookie_manager: EncryptedCookieManager = Depends(cookie_manager),  # noqa: B008
    ) -> CallbackTargetResponse:
        """Handle the OAuth callback by exchanging the authorization code for tokens."""
        stored_state = cookie_manager.get_cookie(
            key=MAASOAuth2Cookie.AUTH_STATE
        )
        stored_nonce = cookie_manager.get_cookie(
            key=MAASOAuth2Cookie.AUTH_NONCE
        )
        if not stored_state or not stored_nonce or stored_state != state:
            raise UnauthorizedException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Invalid or missing OAuth state/nonce.",
                    )
                ]
            )

        tokens = await services.external_oauth.get_callback(
            code=code, nonce=stored_nonce
        )
        cookie_manager.set_auth_cookie(
            value=tokens.access_token
            if isinstance(tokens.access_token, str)
            else tokens.access_token.encoded,
            key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN,
        )
        cookie_manager.set_auth_cookie(
            value=tokens.id_token.encoded,
            key=MAASOAuth2Cookie.OAUTH2_ID_TOKEN,
        )
        cookie_manager.set_auth_cookie(
            value=tokens.refresh_token,
            key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN,
        )
        return CallbackTargetResponse.from_state(state=state)

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
    ) -> OAuthProvidersListResponse:
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
            204: {},
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

    @handler(
        path="/auth/sessions",
        methods=["POST"],
        tags=TAGS,
        responses={204: {}},
        status_code=204,
    )
    async def create_session(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        cookie_manager: EncryptedCookieManager = Depends(cookie_manager),  # noqa: B008
    ) -> None:
        assert authenticated_user is not None
        session = await services.django_session.create_session(
            user_id=authenticated_user.id
        )
        csrf_token = secrets.token_urlsafe(32)
        cookie_manager.set_unsafe_cookie("csrftoken", csrf_token)
        cookie_manager.set_unsafe_cookie(
            "sessionid",
            session.session_key,
            httponly=True,
            expires=session.expire_date,
        )

    @handler(
        path="/auth/sessions:extend",
        methods=["POST"],
        tags=TAGS,
        responses={204: {}, 400: {"model": BadRequestBodyResponse}},
        status_code=204,
    )
    async def extend_session(
        self,
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
        authenticated_user: AuthenticatedUser | None = Depends(  # noqa: B008
            get_authenticated_user
        ),
        cookie_manager: EncryptedCookieManager = Depends(cookie_manager),  # noqa: B008
    ) -> Response:
        assert authenticated_user is not None
        session_id = cookie_manager.get_unsafe_cookie(key="sessionid")
        if not session_id:
            raise BadRequestException(
                details=[
                    BaseExceptionDetail(
                        type=INVALID_TOKEN_VIOLATION_TYPE,
                        message="Session cookie is missing.",
                    )
                ]
            )
        await services.django_session.extend_session(session_key=session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @handler(
        path="/auth/logout",
        methods=["POST"],
        tags=TAGS,
        responses={
            204: {},
        },
        status_code=204,
    )
    async def logout(
        self,
        cookie_manager: EncryptedCookieManager = Depends(cookie_manager),  # noqa: B008
        services: ServiceCollectionV3 = Depends(services),  # noqa: B008
    ) -> None:
        id_token, refresh_token, session_key = (
            cookie_manager.get_cookie(key=MAASOAuth2Cookie.OAUTH2_ID_TOKEN),
            cookie_manager.get_cookie(
                key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN
            ),
            cookie_manager.get_unsafe_cookie(key="sessionid"),
        )
        if id_token and refresh_token:
            await services.external_oauth.revoke_token(
                id_token=id_token, refresh_token=refresh_token
            )
        if session_key:
            await services.django_session.delete_session(
                session_key=session_key
            )

        cookie_manager.clear_cookie(key=MAASOAuth2Cookie.OAUTH2_ID_TOKEN)
        cookie_manager.clear_cookie(key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN)
        cookie_manager.clear_cookie(key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN)
        cookie_manager.clear_cookie(key="sessionid")
        cookie_manager.clear_cookie(key="csrftoken")
