# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import abc
from dataclasses import dataclass
from typing import Callable

from httpx import AsyncClient
import pytest

from maascommon.openfga.base import MAASResourceEntitlement


@dataclass
class Endpoint:
    method: str
    path: str
    permission: MAASResourceEntitlement | None = None


@pytest.mark.asyncio
class ApiCommonTests(abc.ABC):
    @pytest.fixture
    @abc.abstractmethod
    def endpoints_with_authorization(self) -> list[Endpoint]:
        """The subclass should return a list of endpoints that need authorization."""

    @pytest.fixture
    def endpoints_with_authentication_only(self) -> list[Endpoint]:
        """The subclass should return a list of endpoints that need authentication only."""
        return []

    async def test_endpoints_require_authorization_ok(
        self,
        endpoints_with_authorization: list[Endpoint],
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        for endpoint in endpoints_with_authorization:
            assert endpoint.permission is not None, (
                f"Endpoint {endpoint.path} in endpoints_with_authorization should have a permission specified."
            )
            client = mocked_api_client_user_with_permissions(
                endpoint.permission,
            )
            response = await client.request(endpoint.method, endpoint.path)
            # The endpoints can crash with other errors, but they should not fail with authentication/authorization errors.
            assert response.status_code not in (401, 403), (
                f"Endpoint {endpoint.method} {endpoint.path} should be accessible with correct permissions, but got {response.status_code}"
            )

    async def test_endpoints_require_authorization_forbidden(
        self,
        endpoints_with_authorization: list[Endpoint],
        mocked_api_client: AsyncClient,
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        for endpoint in endpoints_with_authorization:
            client = mocked_api_client_user_with_permissions()
            response = await mocked_api_client.request(
                endpoint.method, endpoint.path
            )
            assert response.status_code == 401, (
                f"Endpoint {endpoint.method} {endpoint.path} should require authentication, but got {response.status_code}"
            )

            response = await client.request(endpoint.method, endpoint.path)
            assert response.status_code == 403, (
                f"Endpoint {endpoint.method} {endpoint.path} should require authorization, but got {response.status_code}"
            )

    async def test_endpoints_require_authentication_only(
        self,
        endpoints_with_authentication_only: list[Endpoint],
        mocked_api_client_user_with_permissions: Callable[..., AsyncClient],
    ):
        client = mocked_api_client_user_with_permissions()

        for endpoint in endpoints_with_authentication_only:
            response = await client.request(endpoint.method, endpoint.path)
            # The endpoints can crash with other errors, but they should not fail with authentication/authorization errors.
            assert response.status_code not in (401, 403), (
                f"Endpoint {endpoint.method} {endpoint.path} should be accessible with authentication only, but got {response.status_code}"
            )
