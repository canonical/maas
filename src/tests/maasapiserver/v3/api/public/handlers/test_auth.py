#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from json import dumps as _dumps
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from jose import jwt
from macaroonbakery.bakery import Macaroon
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.external_auth import (
    OAuthProviderRequest,
    OAuthTokenTypeChoices,
)
from maasapiserver.v3.api.public.models.responses.oauth2 import (
    CallbackTargetResponse,
    OAuthProviderResponse,
    OAuthProvidersListResponse,
    PreLoginInfoResponse,
    TokenResponse,
)
from maasapiserver.v3.auth.cookie_manager import MAASOAuth2Cookie
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthIDToken,
    OAuthInitiateData,
    OAuthTokenData,
)
from maasservicelayer.auth.jwt import JWT, UserRole
from maasservicelayer.auth.oidc_jwt import OAuthAccessToken
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BadGatewayException,
    BaseExceptionDetail,
    ConflictException,
    DischargeRequiredException,
    PreconditionFailedException,
    UnauthorizedException,
)
from maasservicelayer.exceptions.constants import (
    CONFLICT_VIOLATION_TYPE,
    ETAG_PRECONDITION_VIOLATION_TYPE,
    INVALID_TOKEN_VIOLATION_TYPE,
    MISSING_PROVIDER_CONFIG_VIOLATION_TYPE,
    PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
    UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.django_session import DjangoSession
from maasservicelayer.models.external_auth import (
    AccessTokenType,
    OAuthProvider,
    ProviderMetadata,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.auth import AuthService, AuthTokens
from maasservicelayer.services.django_session import DjangoSessionService
from maasservicelayer.services.external_auth import (
    ExternalAuthService,
    ExternalOAuthService,
)
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow

TEST_PROVIDER_1 = OAuthProvider(
    id=1,
    created=utcnow(),
    updated=utcnow(),
    name="test_provider_1",
    client_id="test_client_id_1",
    client_secret="test_secret_1",
    issuer_url="https://example1.com",
    redirect_uri="https://example.com/callback",
    scopes="openid email profile",
    enabled=True,
    token_type=AccessTokenType.JWT,
    metadata=ProviderMetadata(
        authorization_endpoint="",
        token_endpoint="",
        jwks_uri="",
    ),
)

TEST_PROVIDER_2 = OAuthProvider(
    id=2,
    created=utcnow(),
    updated=utcnow(),
    name="test_provider_2",
    client_id="test_client_id_2",
    client_secret="test_secret_2",
    issuer_url="https://example2.com",
    redirect_uri="https://example2.com/callback",
    scopes="openid email profile",
    enabled=True,
    token_type=AccessTokenType.OPAQUE,
    metadata=ProviderMetadata(
        authorization_endpoint="https://example2.com/authorize",
        token_endpoint="https://example2.com/token",
        jwks_uri="https://example2.com/.well-known/jwks.json",
    ),
)


@pytest.mark.asyncio
class TestAuthApi:
    BASE_PATH = f"{V3_API_PREFIX}/auth"

    # GET /auth/login
    async def test_get(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.users = Mock(UsersService)
        services_mock.users.has_users.return_value = False
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/login")
        assert response.status_code == 200
        pre_login_info = PreLoginInfoResponse(**response.json())
        assert pre_login_info.is_authenticated is True
        assert pre_login_info.no_users is True

    # POST /auth/login
    async def test_post(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login.return_value = AuthTokens(
            access_token=JWT.create("key", "username", 0, [UserRole.USER]),
            refresh_token="abc123",
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login",
            data={"username": "username", "password": "test"},
        )
        assert response.status_code == 200

        token_response = TokenResponse(**response.json())
        assert token_response.token_type == "bearer"
        assert (
            jwt.get_unverified_claims(token_response.access_token)["sub"]
            == "username"
        )
        assert token_response.refresh_token == "abc123"

    async def test_post_validation_failed(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login", data={"username": "username"}
        )

        assert response.status_code == 422

    async def test_post_discharge_required_exception(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user_rbac: AsyncClient,
    ) -> None:
        services_mock.external_auth = Mock(ExternalAuthService)
        services_mock.external_auth.raise_discharge_required_exception.side_effect = DischargeRequiredException(
            macaroon=Mock(Macaroon)
        )

        # we have to mock json.dumps as it doesn't know how to deal with Mock objects
        def custom_json_dumps(*args, **kwargs):
            return _dumps(*args, **(kwargs | {"default": lambda obj: "mock"}))

        with patch("json.dumps", custom_json_dumps):
            response = await mocked_api_client_user_rbac.post(
                f"{self.BASE_PATH}/login",
                data={"username": "username", "password": "test"},
            )

        services_mock.external_auth.raise_discharge_required_exception.assert_called_once()
        assert response.status_code == 401
        json_response = response.json()
        assert json_response["Code"] == "macaroon discharge required"

    async def test_post_wrong_credentials(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login.side_effect = UnauthorizedException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
                    message="The credentials are not matching or the user does not exist",
                )
            ]
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login",
            data={"username": "username", "password": "wrong"},
        )
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

    # GET /auth/access_token
    async def test_get_access_token_with_jwt(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.access_token.return_value = JWT.create(
            "key", "username", 0, [UserRole.USER]
        )

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/access_token",
        )
        assert response.status_code == 200

        token_response = TokenResponse(**response.json())
        assert token_response.kind == "Tokens"
        assert token_response.token_type == "bearer"
        decoded_token = jwt.get_unverified_claims(token_response.access_token)
        assert decoded_token["sub"] == "username"
        assert decoded_token["user_id"] == 0
        assert token_response.refresh_token is None

    async def test_get_access_token_with_session_id(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_session_id: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.access_token.return_value = JWT.create(
            "key", "username", 0, [UserRole.USER]
        )
        response = await mocked_api_client_session_id.get(
            f"{self.BASE_PATH}/access_token",
        )
        assert response.status_code == 200

        token_response = TokenResponse(**response.json())
        assert token_response.kind == "Tokens"
        assert token_response.token_type == "bearer"
        decoded_token = jwt.get_unverified_claims(token_response.access_token)
        assert decoded_token["sub"] == "username"
        assert decoded_token["user_id"] == 0
        assert token_response.refresh_token is None

    @pytest.mark.skip
    async def test_get_access_token_with_macaroon(self):
        pass

    async def test_get_access_token_not_logged_in(
        self,
        mocked_api_client: AsyncClient,
    ) -> None:
        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/access_token"
        )
        assert response.status_code == 401
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 401

    # GET /auth/login_info
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.set_auth_cookie"
    )
    async def test_get_oauth_initiate_success_oidc(
        self,
        cookie_manager_set_auth_cookie: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        cookie_manager_set_auth_cookie.return_value = None
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.users = Mock(UsersService)
        services_mock.users.is_oidc_user.return_value = True
        client_mock = Mock(OAuth2Client(TEST_PROVIDER_1))
        returned_data = OAuthInitiateData(
            authorization_url="https://example.com/auth?state=abc123&nonce=def123",
            state="abc123",
            nonce="def123",
        )
        client_mock.generate_authorization_url.return_value = returned_data
        client_mock.get_provider_name.return_value = TEST_PROVIDER_1.name
        services_mock.external_oauth.get_client.return_value = client_mock

        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/login_info?email=test@example.com&redirect_target=/machines"
        )

        assert response.status_code == 200
        data = response.json()
        assert (
            data["auth_url"]
            == "https://example.com/auth?state=abc123&nonce=def123"
        )
        assert data["provider_name"] == TEST_PROVIDER_1.name
        cookie_manager_set_auth_cookie.assert_any_call(
            value="abc123", key=MAASOAuth2Cookie.AUTH_STATE
        )
        cookie_manager_set_auth_cookie.assert_any_call(
            value="def123", key=MAASOAuth2Cookie.AUTH_NONCE
        )

    async def test_get_oauth_initiate_not_configured(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.users = Mock(UsersService)
        services_mock.users.is_oidc_user.return_value = True
        services_mock.external_oauth.get_client.side_effect = (
            ConflictException()
        )
        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/login_info?email=test@example.com"
        )

        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_get_oauth_initiate_not_oidc_user(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.users = Mock(UsersService)
        services_mock.users.is_oidc_user.return_value = False

        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/login_info?email=test@example.com"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auth_url"] is None
        assert data["provider_name"] is None
        assert data["is_oidc"] is False

    # GET /auth/oauth/providers
    async def test_list_oauth_providers_200_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.list.return_value = ListResult[
            OAuthProvider
        ](items=[TEST_PROVIDER_1], total=1)

        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/oauth/providers?size=1",
        )

        assert response.status_code == 200

        providers_response = OAuthProvidersListResponse(**response.json())

        assert providers_response.kind == "AuthProvidersList"
        assert len(providers_response.items) == 1
        assert providers_response.total == 1
        assert providers_response.next is None

    async def test_list_oauth_providers_200_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.list.return_value = ListResult[
            OAuthProvider
        ](items=[TEST_PROVIDER_1, TEST_PROVIDER_2], total=2)

        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/oauth/providers?size=1",
        )

        assert response.status_code == 200

        providers_response = OAuthProvidersListResponse(**response.json())

        assert providers_response.kind == "AuthProvidersList"
        assert len(providers_response.items) == 2
        assert providers_response.total == 2
        assert (
            providers_response.next
            == f"{self.BASE_PATH}/oauth/providers?page=2&size=1"
        )

    # PUT /auth/oauth/providers/:provider_id
    async def test_update_oauth_provider_success(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        request_body = OAuthProviderRequest(
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            token_type=OAuthTokenTypeChoices.JWT,
            enabled=True,
        )
        updated_provider = OAuthProvider(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="test_provider",
            client_id="new_client_id",
            client_secret="new_secret",
            issuer_url="https://new-example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            token_type=AccessTokenType.JWT,
            enabled=True,
            metadata=ProviderMetadata(
                authorization_endpoint="",
                token_endpoint="",
                jwks_uri="",
            ),
        )
        services_mock.external_oauth.update_provider.return_value = (
            updated_provider
        )
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/oauth/providers/1",
            json=jsonable_encoder(request_body.dict()),
        )

        assert response.status_code == 200
        updated_provider_response = OAuthProviderResponse(**response.json())
        assert (
            updated_provider_response.client_id == updated_provider.client_id
        )
        assert (
            updated_provider_response.client_secret
            == updated_provider.client_secret
        )
        assert (
            updated_provider_response.issuer_url == updated_provider.issuer_url
        )
        assert updated_provider_response.token_type == request_body.token_type

    async def test_update_oauth_provider_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        request_body = OAuthProviderRequest(
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            token_type=OAuthTokenTypeChoices.JWT,
        )
        services_mock.external_oauth.update_provider.return_value = None
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/oauth/providers/1",
            json=jsonable_encoder(request_body.dict()),
        )

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_update_oauth_provider_invalid_body(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        request_body = {
            "name": "test_provider",
            "client_id": "test_client_id",
            "client_secret": "test_secret",
            "issuer_url": "invalid_url",
            "redirect_uri": "https://example.com/callback",
            "scopes": "openid email profile",
            "enabled": True,
        }
        services_mock.external_oauth.update_provider.return_value = None
        response = await mocked_api_client_admin.put(
            f"{self.BASE_PATH}/oauth/providers/1",
            json=jsonable_encoder(request_body),
        )

        assert response.status_code == 422
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    # POST /auth/oauth/providers
    async def test_create_oauth_provider_success(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        request_body = OAuthProviderRequest(
            name="test_provider_1",
            client_id="test_client_id_1",
            client_secret="test_secret_1",
            issuer_url="https://example1.com",
            redirect_uri="https://example1.com/callback",
            scopes="openid email profile",
            enabled=True,
            token_type=OAuthTokenTypeChoices.JWT,
        )
        created_provider = TEST_PROVIDER_1
        services_mock.external_oauth.create.return_value = created_provider

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/oauth/providers",
            json=jsonable_encoder(request_body.dict()),
        )
        assert response.status_code == 200
        provider_response = OAuthProviderResponse(**response.json())
        assert provider_response.client_id == request_body.client_id
        assert provider_response.client_secret == request_body.client_secret
        assert provider_response.issuer_url == request_body.issuer_url

    async def test_create_oauth_provider_already_exists(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.create.side_effect = AlreadyExistsException(
            details=[
                BaseExceptionDetail(
                    type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                    message="A resource with such identifiers already exist.",
                )
            ]
        )
        request_body = OAuthProviderRequest(
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            token_type=OAuthTokenTypeChoices.JWT,
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/oauth/providers",
            json=jsonable_encoder(request_body.dict()),
        )
        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_create_oauth_provider_conflict(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.create.side_effect = ConflictException(
            details=[
                BaseExceptionDetail(
                    type=CONFLICT_VIOLATION_TYPE,
                    message="An enabled OIDC provider already exists. Please disable it first.",
                )
            ]
        )
        request_body = OAuthProviderRequest(
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            token_type=OAuthTokenTypeChoices.JWT,
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/oauth/providers",
            json=jsonable_encoder(request_body.dict()),
        )
        assert response.status_code == 409
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_create_oauth_provider_bad_gateway(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.create.side_effect = BadGatewayException(
            details=[
                BaseExceptionDetail(
                    type=PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
                    message="Failed to fetch provider metadata from OIDC server.",
                )
            ]
        )
        request_body = OAuthProviderRequest(
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            token_type=OAuthTokenTypeChoices.JWT,
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/oauth/providers",
            json=jsonable_encoder(request_body.dict()),
        )
        assert response.status_code == 502
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 502

    # DELETE /auth/oauth/providers/:provider_id
    async def test_delete_oauth_provider(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/oauth/providers/1"
        )
        assert response.status_code == 204

    async def test_delete_oauth_provider_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/oauth/providers/1",
            headers={"if-match": "my_etag"},
        )
        assert response.status_code == 204

    async def test_delete_oauth_provider_wrong_etag_error(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.delete_by_id.side_effect = [
            PreconditionFailedException(
                details=[
                    BaseExceptionDetail(
                        type=ETAG_PRECONDITION_VIOLATION_TYPE,
                        message="The etag 'wrong_etag' did not match etag 'my_etag'.",
                    )
                ]
            ),
            None,
        ]
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/oauth/providers/1",
            headers={"if-match": "wrong_etag"},
        )
        assert response.status_code == 412
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

    async def test_get_active_oauth_provider_success(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        created_provider = OAuthProvider(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            name="test_provider",
            client_id="test_client_id",
            client_secret="test_secret",
            issuer_url="https://example.com",
            redirect_uri="https://example.com/callback",
            scopes="openid email profile",
            enabled=True,
            token_type=AccessTokenType.JWT,
            metadata=ProviderMetadata(
                authorization_endpoint="",
                token_endpoint="",
                jwks_uri="",
            ),
        )
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.users = Mock(UsersService)
        services_mock.external_oauth.get_provider.return_value = (
            created_provider
        )
        services_mock.users.count_by_provider.return_value = 5

        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/oauth:is_active"
        )
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "AuthProvider",
            "name": created_provider.name,
            "client_id": created_provider.client_id,
            "client_secret": created_provider.client_secret,
            "issuer_url": created_provider.issuer_url,
            "redirect_uri": created_provider.redirect_uri,
            "scopes": created_provider.scopes,
            "enabled": created_provider.enabled,
            "id": created_provider.id,
            "metadata": created_provider.metadata,
            "token_type": "JWT",
            "user_count": 5,
        }

    async def test_get_active_oauth_provider_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.get_provider.return_value = None
        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/oauth:is_active"
        )
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_oauth_provider_by_id_success(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.users = Mock(UsersService)
        services_mock.external_oauth.get_by_id.return_value = TEST_PROVIDER_1
        services_mock.users.count_by_provider.return_value = 3

        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/oauth/providers/1",
        )

        assert response.status_code == 200

        provider_response = OAuthProviderResponse(**response.json())

        assert provider_response.kind == "AuthProvider"
        assert provider_response.id == TEST_PROVIDER_1.id
        assert provider_response.name == TEST_PROVIDER_1.name
        assert provider_response.client_id == TEST_PROVIDER_1.client_id
        assert provider_response.user_count == 3

    async def test_get_oauth_provider_by_id_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ):
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.get_by_id.return_value = None

        response = await mocked_api_client_admin.get(
            f"{self.BASE_PATH}/oauth/providers/999",
        )

        assert response.status_code == 404

        error_response = ErrorBodyResponse(**response.json())
        details = error_response.details
        assert details is not None
        assert error_response.kind == "Error"
        assert error_response.code == 404
        assert details[0].type == MISSING_PROVIDER_CONFIG_VIOLATION_TYPE
        assert (
            details[0].message
            == "No OIDC provider with the given ID was found."
        )

    # GET /auth/oauth/callback
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.set_auth_cookie"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_cookie"
    )
    async def test_handle_oauth_callback_success_when_access_token_is_string(
        self,
        cookie_manager_get_cookie: MagicMock,
        cookie_manager_set_auth_cookie: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        # Sample state with /machines as redirect target
        state = "L21hY2hpbmVz.R8kFv9s1Xq2aL3pTz4uM0wY7"
        cookie_manager_get_cookie.side_effect = [
            state,
            "stored_nonce",
        ]
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.get_callback.return_value = (
            OAuthTokenData(
                access_token="abc123",
                id_token=OAuthIDToken(
                    claims=Mock(),
                    encoded="def123",
                    provider=TEST_PROVIDER_1,
                ),
                refresh_token="ghi123",
            )
        )

        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/oauth/callback?state={state}&code=auth_code"
        )
        assert response.status_code == 200
        target = CallbackTargetResponse(**response.json())
        assert target.redirect_target == "/machines"
        assert target.kind == "CallbackTarget"
        services_mock.external_oauth.get_callback.assert_called_once_with(
            code="auth_code", nonce="stored_nonce"
        )
        cookie_manager_set_auth_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN, value="abc123"
        )
        cookie_manager_set_auth_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_ID_TOKEN, value="def123"
        )
        cookie_manager_set_auth_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN, value="ghi123"
        )

    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.set_auth_cookie"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_cookie"
    )
    async def test_handle_oauth_callback_success_when_access_token_is_not_string(
        self,
        cookie_manager_get_cookie: MagicMock,
        cookie_manager_set_auth_cookie: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        # Sample state with /machines as redirect target
        state = "L21hY2hpbmVz.R8kFv9s1Xq2aL3pTz4uM0wY7"
        cookie_manager_get_cookie.side_effect = [
            state,
            "stored_nonce",
        ]
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.get_callback.return_value = (
            OAuthTokenData(
                access_token=OAuthAccessToken(
                    claims=Mock(),
                    encoded="abc123",
                    provider=TEST_PROVIDER_1,
                ),
                id_token=OAuthIDToken(
                    claims=Mock(),
                    encoded="def123",
                    provider=TEST_PROVIDER_1,
                ),
                refresh_token="ghi123",
            )
        )

        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/oauth/callback?state={state}&code=auth_code"
        )
        assert response.status_code == 200
        target = CallbackTargetResponse(**response.json())
        assert target.redirect_target == "/machines"
        assert target.kind == "CallbackTarget"
        services_mock.external_oauth.get_callback.assert_called_once_with(
            code="auth_code", nonce="stored_nonce"
        )

        cookie_manager_set_auth_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN, value="abc123"
        )
        cookie_manager_set_auth_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_ID_TOKEN, value="def123"
        )
        cookie_manager_set_auth_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN, value="ghi123"
        )

    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_cookie"
    )
    async def test_handle_oauth_callback_invalid_state(
        self,
        cookie_manager_get_cookie: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.external_oauth = Mock(ExternalOAuthService)
        cookie_manager_get_cookie.side_effect = [
            "stored_state",
            "stored_nonce",
        ]

        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/oauth/callback?state=some_state&code=auth_code"
        )

        error_response = ErrorBodyResponse(**response.json())
        details = error_response.details

        services_mock.external_oauth.get_callback.assert_not_called()
        assert response.status_code == 401
        assert error_response.kind == "Error"
        assert error_response.code == 401
        assert details is not None
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
        assert details[0].message == "Invalid or missing OAuth state/nonce."

    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.clear_cookie"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_cookie"
    )
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_unsafe_cookie"
    )
    async def test_get_logout_success(
        self,
        cookie_manager_get_unsafe_cookie: MagicMock,
        cookie_manager_get_cookie: MagicMock,
        cookie_manager_clear_cookie: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.django_session = Mock(DjangoSessionService)
        services_mock.django_session.delete_session.return_value = None
        cookie_manager_get_unsafe_cookie.return_value = "sessionid123"
        cookie_manager_get_cookie.side_effect = ["abc123", "def123"]
        cookie_manager_clear_cookie.return_value = None
        services_mock.external_oauth.revoke_token = AsyncMock(
            return_value=None
        )

        response = await mocked_api_client.post(f"{self.BASE_PATH}/logout")

        cookie_manager_clear_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_ID_TOKEN
        )
        cookie_manager_clear_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_ACCESS_TOKEN
        )
        cookie_manager_clear_cookie.assert_any_call(
            key=MAASOAuth2Cookie.OAUTH2_REFRESH_TOKEN
        )
        cookie_manager_clear_cookie.assert_any_call(key="sessionid")
        cookie_manager_clear_cookie.assert_any_call(key="csrftoken")
        services_mock.external_oauth.revoke_token.assert_awaited_once_with(
            id_token="abc123", refresh_token="def123"
        )
        assert response.status_code == 204

    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.set_unsafe_cookie"
    )
    @patch("maasapiserver.v3.api.public.handlers.auth.secrets.token_urlsafe")
    async def test_post_create_session_204(
        self,
        token_urlsafe_mock: MagicMock,
        set_unsafe_cookie_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        test_session = DjangoSession(
            session_key="sessionid123",
            expire_date=utcnow() + timedelta(hours=1),
            session_data="sessiondata",
        )
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.django_session = Mock(DjangoSessionService)
        services_mock.django_session.create_session.return_value = test_session
        token_urlsafe_mock.return_value = "randomcsrftoken"
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/sessions",
        )
        assert response.status_code == 204

        set_unsafe_cookie_mock.assert_any_call(
            "sessionid",
            "sessionid123",
            httponly=True,
            expires=test_session.expire_date,
        )
        set_unsafe_cookie_mock.assert_any_call("csrftoken", "randomcsrftoken")

    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_unsafe_cookie"
    )
    async def test_post_extend_session_204(
        self,
        get_unsafe_cookie_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        get_unsafe_cookie_mock.return_value = "sessionid123"
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.django_session = Mock(DjangoSessionService)
        services_mock.django_session.extend_session.return_value = None
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/sessions:extend",
        )
        assert response.status_code == 204
        services_mock.django_session.extend_session.assert_awaited_once_with(
            session_key="sessionid123",
        )

    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.get_unsafe_cookie"
    )
    async def test_post_extend_session_400(
        self,
        get_unsafe_cookie_mock: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.django_session = Mock(DjangoSessionService)
        get_unsafe_cookie_mock.return_value = None
        services_mock.django_session.extend_session.return_value = None
        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}/sessions:extend",
        )
        assert response.status_code == 400
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        details = error_response.details
        assert details is not None
        assert details[0].type == INVALID_TOKEN_VIOLATION_TYPE
        assert details[0].message == "Session cookie is missing."
