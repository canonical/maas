import abc
from dataclasses import dataclass

from httpx import AsyncClient
import pytest


@dataclass
class Endpoint:
    method: str
    path: str


@pytest.mark.asyncio
class ApiCommonTests(abc.ABC):

    @pytest.fixture
    @abc.abstractmethod
    def user_endpoints(self) -> list[Endpoint]:
        """The subclass should return a list of endpoints that need the `user` permission."""

    @pytest.fixture
    @abc.abstractmethod
    def admin_endpoints(self) -> list[Endpoint]:
        """The subclass should return a list of endpoints that need the `admin` permission."""

    async def test_user_endpoints_forbidden(
        self,
        user_endpoints: list[Endpoint],
        mocked_api_client: AsyncClient,
    ):
        for endpoint in user_endpoints:
            response = await mocked_api_client.request(
                endpoint.method, endpoint.path
            )
            assert response.status_code == 401

    async def test_admin_endpoints_forbidden(
        self,
        admin_endpoints: list[Endpoint],
        mocked_api_client: AsyncClient,
        mocked_api_client_user: AsyncClient,
    ):
        for endpoint in admin_endpoints:
            response = await mocked_api_client.request(
                endpoint.method, endpoint.path
            )
            assert response.status_code == 401

            response = await mocked_api_client_user.request(
                endpoint.method, endpoint.path
            )
            assert response.status_code == 403
