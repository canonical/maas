#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from json import dumps as _dumps
from unittest.mock import MagicMock, Mock, patch

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
from jose import jwt
from macaroonbakery.bakery import Macaroon
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.external_auth import (
    OAuthProviderRequest,
)
from maasapiserver.v3.api.public.models.responses.oauth2 import (
    AccessTokenResponse,
    OAuthProviderResponse,
    OAuthProvidersListResponse,
)
from maasapiserver.v3.auth.cookie_manager import MAASOAuth2Cookie
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.auth.external_oauth import (
    OAuth2Client,
    OAuthInitiateData,
)
from maasservicelayer.auth.jwt import JWT, UserRole
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
    PROVIDER_DISCOVERY_FAILED_VIOLATION_TYPE,
    UNEXISTING_USER_OR_INVALID_CREDENTIALS_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.external_auth import (
    OAuthProvider,
    ProviderMetadata,
)
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.auth import AuthService
from maasservicelayer.services.external_auth import (
    ExternalAuthService,
    ExternalOAuthService,
)
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
    metadata=ProviderMetadata(
        authorization_endpoint="https://example2.com/authorize",
        token_endpoint="https://example2.com/token",
        jwks_uri="https://example2.com/.well-known/jwks.json",
    ),
)


@pytest.mark.asyncio
class TestAuthApi:
    BASE_PATH = f"{V3_API_PREFIX}/auth"

    # POST /auth/login
    async def test_post(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        services_mock.auth = Mock(AuthService)
        services_mock.auth.login.return_value = JWT.create(
            "key", "username", 0, [UserRole.USER]
        )
        response = await mocked_api_client.post(
            f"{self.BASE_PATH}/login",
            data={"username": "username", "password": "test"},
        )
        assert response.status_code == 200

        token_response = AccessTokenResponse(**response.json())
        assert token_response.token_type == "bearer"
        assert (
            jwt.get_unverified_claims(token_response.access_token)["sub"]
            == "username"
        )

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

        token_response = AccessTokenResponse(**response.json())
        assert token_response.kind == "AccessToken"
        assert token_response.token_type == "bearer"
        decoded_token = jwt.get_unverified_claims(token_response.access_token)
        assert decoded_token["sub"] == "username"
        assert decoded_token["user_id"] == 0

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

        token_response = AccessTokenResponse(**response.json())
        assert token_response.kind == "AccessToken"
        assert token_response.token_type == "bearer"
        decoded_token = jwt.get_unverified_claims(token_response.access_token)
        assert decoded_token["sub"] == "username"
        assert decoded_token["user_id"] == 0

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

    # GET /auth/oauth/authorization_url
    @patch(
        "maasapiserver.v3.api.public.handlers.auth.EncryptedCookieManager.set_auth_cookie"
    )
    async def test_get_oauth_initiate_success(
        self,
        cookie_manager_set_auth_cookie: MagicMock,
        services_mock: ServiceCollectionV3,
        mocked_api_client: AsyncClient,
    ) -> None:
        cookie_manager_set_auth_cookie.return_value = None
        services_mock.external_oauth = Mock(ExternalOAuthService)
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
            f"{self.BASE_PATH}/oauth/authorization_url"
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
        services_mock.external_oauth.get_client.return_value = None

        response = await mocked_api_client.get(
            f"{self.BASE_PATH}/oauth/authorization_url"
        )

        assert response.status_code == 404
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

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

    # POST /auth/oauth
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
                    type=PROVIDER_DISCOVERY_FAILED_VIOLATION_TYPE,
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
        )

        response = await mocked_api_client_admin.post(
            f"{self.BASE_PATH}/oauth/providers",
            json=jsonable_encoder(request_body.dict()),
        )
        assert response.status_code == 502
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 502

    # DELETE /auth/oauth/:provider_id
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
            metadata=ProviderMetadata(
                authorization_endpoint="",
                token_endpoint="",
                jwks_uri="",
            ),
        )
        services_mock.external_oauth = Mock(ExternalOAuthService)
        services_mock.external_oauth.get_provider.return_value = (
            created_provider
        )
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
