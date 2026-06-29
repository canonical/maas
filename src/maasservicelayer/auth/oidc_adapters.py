# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse

from httpx import AsyncClient

from maasservicelayer.models.external_auth import (
    OAuthProvider,
    ProviderVendorType,
)
from maasservicelayer.utils.date import utcnow

# Refresh the cached token slightly before it expires to avoid races.
TOKEN_EXPIRY_LEEWAY = 30
DEFAULT_TOKEN_TTL = 3600


class BaseProviderAdapter(ABC):
    """Queries a provider's user-management API using the client credentials
    (machine-to-machine) flow, to verify whether a user is still valid.
    """

    def __init__(self, provider: OAuthProvider, http_client: AsyncClient):
        self.provider = provider
        self._http = http_client
        self._token: str | None = None
        self._token_expiry: float = 0.0

    async def get_token(self) -> str:
        now = utcnow().timestamp()
        if self._token and now < self._token_expiry - TOKEN_EXPIRY_LEEWAY:
            return self._token
        result = await self._token_request(
            self._token_endpoint(), self._token_request_body()
        )
        token: str = result["access_token"]
        self._token = token
        self._token_expiry = now + result.get("expires_in", DEFAULT_TOKEN_TTL)
        return token

    def _token_endpoint(self) -> str:
        return self.provider.metadata.token_endpoint

    @abstractmethod
    def _token_request_body(self) -> dict[str, str]:
        """Provider-specific body for the client credentials token request."""

    async def _token_request(
        self, url: str, data: dict[str, str]
    ) -> dict[str, Any]:
        response = await self._http.post(url, data=data)
        response.raise_for_status()
        return response.json()

    async def _get(
        self,
        url: str,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        token = await self.get_token()
        request_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)
        response = await self._http.get(
            url,
            params=params,
            headers=request_headers,
        )
        response.raise_for_status()
        return response.json()

    @abstractmethod
    async def user_is_active(self, email: str) -> bool:
        """Whether a user with the given email exists and is active."""


class EntraIDAdapter(BaseProviderAdapter):
    """Microsoft Entra ID (Azure AD), via the Microsoft Graph API."""

    GRAPH_SCOPE = "https://graph.microsoft.com/.default"
    GRAPH_URL = "https://graph.microsoft.com/v1.0"

    def _token_request_body(self) -> dict[str, str]:
        return {
            "grant_type": "client_credentials",
            "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret,
            "scope": self.GRAPH_SCOPE,
        }

    async def user_is_active(self, email: str) -> bool:
        filter_expr = (
            f"(startswith(mail,'{email}') or "
            f"startswith(userPrincipalName,'{email}'))"
        )
        result = await self._get(
            f"{self.GRAPH_URL}/users",
            params={
                "$filter": filter_expr,
                "$select": "accountEnabled",
                "$count": "true",
                "$top": "1",
            },
            headers={"ConsistencyLevel": "eventual"},
        )
        users = result.get("value") or []
        return bool(users) and bool(users[0].get("accountEnabled"))


class Auth0Adapter(BaseProviderAdapter):
    """Auth0, via the Management API."""

    def _token_request_body(self) -> dict[str, str]:
        default_audience = f"{self.provider.issuer_url}/api/v2/"
        return {
            "grant_type": "client_credentials",
            "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret,
            "audience": default_audience,
        }

    async def user_is_active(self, email: str) -> bool:
        result = await self._get(
            f"{self.provider.issuer_url}/api/v2/users",
            params={
                "q": f'email:"{email}"',
                "search_engine": "v3",
            },
        )
        users = result or []
        return bool(users) and not users[0].get("blocked", False)


class KeycloakAdapter(BaseProviderAdapter):
    """Keycloak, via the admin REST API."""

    DEFAULT_SCOPE = "profile email"

    def _realm(self) -> str:
        # issuer_url looks like "{root}/realms/{realm}".
        path = urlparse(self.provider.issuer_url).path.rstrip("/")
        return path.rsplit("/", 1)[-1]

    def _root_url(self) -> str:
        parsed = urlparse(self.provider.issuer_url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _token_request_body(self) -> dict[str, str]:
        return {
            "grant_type": "client_credentials",
            "client_id": self.provider.client_id,
            "client_secret": self.provider.client_secret,
            "scope": self.DEFAULT_SCOPE,
        }

    async def user_is_active(self, email: str) -> bool:
        result = await self._get(
            f"{self._root_url()}/admin/realms/{self._realm()}/users",
            params={"email": email, "exact": "true"},
        )
        users = result or []
        return bool(users) and bool(users[0].get("enabled"))


ADAPTER_BY_VENDOR: dict[ProviderVendorType, type[BaseProviderAdapter]] = {
    ProviderVendorType.ENTRAID: EntraIDAdapter,
    ProviderVendorType.AUTH0: Auth0Adapter,
    ProviderVendorType.KEYCLOAK: KeycloakAdapter,
}


def get_provider_adapter(
    provider: OAuthProvider, http_client: AsyncClient
) -> BaseProviderAdapter | None:
    adapter_cls = ADAPTER_BY_VENDOR.get(provider.vendor)
    if adapter_cls is None:
        return None
    return adapter_cls(provider, http_client)
