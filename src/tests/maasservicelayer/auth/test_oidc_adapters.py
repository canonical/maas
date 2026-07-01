#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock

from httpx import AsyncClient, Request, Response
import pytest

from maasservicelayer.auth.oidc_adapters import (
    Auth0Adapter,
    EntraIDAdapter,
    KeycloakAdapter,
)
from maasservicelayer.exceptions.catalog import BadGatewayException
from maasservicelayer.exceptions.constants import (
    PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE,
)
from maasservicelayer.models.external_auth import (
    AccessTokenType,
    OAuthProvider,
    ProviderMetadata,
    ProviderVendorType,
)

TOKEN_RESPONSE = {"access_token": "m2m-token", "expires_in": 3600}

_REQUEST = Request("GET", "https://provider.example")


def _provider(issuer_url: str) -> OAuthProvider:
    return OAuthProvider(
        id=1,
        issuer_url=issuer_url,
        name="provider",
        client_id="client123",
        client_secret="secret456",
        redirect_uri="https://maas.example/callback",
        token_type=AccessTokenType.JWT,
        scopes="openid email",
        enabled=True,
        vendor=ProviderVendorType.GENERIC,
        metadata=ProviderMetadata(
            authorization_endpoint=f"{issuer_url}/authorize",
            token_endpoint=f"{issuer_url}/token",
            jwks_uri=f"{issuer_url}/jwks",
        ),
    )


def _http_client(get_response: Response) -> AsyncClient:
    client = AsyncMock(spec=AsyncClient)
    client.post.return_value = Response(
        200, json=TOKEN_RESPONSE, request=_REQUEST
    )
    get_response.request = _REQUEST
    client.get.return_value = get_response
    return client


class TestEntraIDAdapter:
    def _adapter(self, get_response: Response) -> EntraIDAdapter:
        provider = _provider("https://login.microsoftonline.com/tenant")
        return EntraIDAdapter(provider, _http_client(get_response))

    async def test_token_request_uses_graph_scope(self):
        adapter = self._adapter(Response(200, json={"value": []}))

        await adapter.get_token()

        _, kwargs = adapter._http.post.call_args
        assert kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "client123",
            "client_secret": "secret456",
            "scope": EntraIDAdapter.GRAPH_SCOPE,
        }

    async def test_user_is_active_true_when_account_enabled(self):
        adapter = self._adapter(
            Response(200, json={"value": [{"accountEnabled": True}]})
        )

        assert await adapter.user_is_active("user@example.com") is True

    async def test_user_is_active_false_when_account_disabled(self):
        adapter = self._adapter(
            Response(200, json={"value": [{"accountEnabled": False}]})
        )

        assert await adapter.user_is_active("user@example.com") is False

    async def test_user_is_active_false_when_not_found(self):
        adapter = self._adapter(Response(200, json={"value": []}))

        assert await adapter.user_is_active("user@example.com") is False


class TestAuth0Adapter:
    def _adapter(self, get_response: Response) -> Auth0Adapter:
        provider = _provider("https://dev-tenant.us.auth0.com")
        return Auth0Adapter(provider, _http_client(get_response))

    async def test_token_request_uses_management_audience(self):
        adapter = self._adapter(Response(200, json=[]))

        await adapter.get_token()

        _, kwargs = adapter._http.post.call_args
        assert kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "client123",
            "client_secret": "secret456",
            "audience": "https://dev-tenant.us.auth0.com/api/v2/",
        }

    async def test_user_is_active_true_when_not_blocked(self):
        adapter = self._adapter(
            Response(200, json=[{"email": "user@example.com"}])
        )

        assert await adapter.user_is_active("user@example.com") is True

    async def test_user_is_active_false_when_blocked(self):
        adapter = self._adapter(Response(200, json=[{"blocked": True}]))

        assert await adapter.user_is_active("user@example.com") is False

    async def test_user_is_active_false_when_not_found(self):
        adapter = self._adapter(Response(200, json=[]))

        assert await adapter.user_is_active("user@example.com") is False


class TestKeycloakAdapter:
    def _adapter(self, get_response: Response) -> KeycloakAdapter:
        provider = _provider("http://keycloak.example:8080/realms/master")
        return KeycloakAdapter(provider, _http_client(get_response))

    async def test_token_request_uses_default_scope(self):
        adapter = self._adapter(Response(200, json=[]))

        await adapter.get_token()

        _, kwargs = adapter._http.post.call_args
        assert kwargs["data"] == {
            "grant_type": "client_credentials",
            "client_id": "client123",
            "client_secret": "secret456",
            "scope": KeycloakAdapter.DEFAULT_SCOPE,
        }

    async def test_user_is_active_queries_realm_admin_endpoint(self):
        adapter = self._adapter(Response(200, json=[{"enabled": True}]))

        await adapter.user_is_active("user@example.com")

        args, _ = adapter._http.get.call_args
        assert args[0] == (
            "http://keycloak.example:8080/admin/realms/master/users"
        )

    async def test_user_is_active_true_when_enabled(self):
        adapter = self._adapter(Response(200, json=[{"enabled": True}]))

        assert await adapter.user_is_active("user@example.com") is True

    async def test_user_is_active_false_when_disabled(self):
        adapter = self._adapter(Response(200, json=[{"enabled": False}]))

        assert await adapter.user_is_active("user@example.com") is False

    async def test_user_is_active_false_when_not_found(self):
        adapter = self._adapter(Response(200, json=[]))

        assert await adapter.user_is_active("user@example.com") is False


class BaseAdapterErrorHandling:
    def _adapter(self, http_client: AsyncClient) -> EntraIDAdapter:
        provider = _provider("https://login.microsoftonline.com/tenant")
        return EntraIDAdapter(provider, http_client)

    async def test_get_token_raises_when_access_token_missing(self):
        client = AsyncMock(spec=AsyncClient)
        client.post.return_value = Response(
            200, json={"expires_in": 3600}, request=_REQUEST
        )
        adapter = self._adapter(client)

        with pytest.raises(BadGatewayException) as exc_info:
            await adapter.get_token()

        assert (
            exc_info.value.details[0].type
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )

    async def test_token_request_raises_on_http_status_error(self):
        client = AsyncMock(spec=AsyncClient)
        client.post.return_value = Response(
            401, json={"error": "invalid_client"}, request=_REQUEST
        )
        adapter = self._adapter(client)

        with pytest.raises(BadGatewayException) as exc_info:
            await adapter.get_token()

        assert (
            exc_info.value.details[0].type
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )

    async def test_get_raises_on_http_status_error(self):
        client = AsyncMock(spec=AsyncClient)
        client.post.return_value = Response(
            200, json=TOKEN_RESPONSE, request=_REQUEST
        )
        client.get.return_value = Response(
            403, json={"error": "forbidden"}, request=_REQUEST
        )
        adapter = self._adapter(client)

        with pytest.raises(BadGatewayException) as exc_info:
            await adapter.user_is_active("user@example.com")

        assert (
            exc_info.value.details[0].type
            == PROVIDER_COMMUNICATION_FAILED_VIOLATION_TYPE
        )
