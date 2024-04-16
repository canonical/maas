import abc
from dataclasses import dataclass

from httpx import AsyncClient
import pytest


@dataclass
class EndpointDetails:
    method: str
    path: str


@dataclass
class ApiEndpointsRoles:
    # endpoints that should be accessed without authentication
    unauthenticated_endpoints: list[EndpointDetails]

    # endpoints that can be accessed with user permissions
    user_endpoints: list[EndpointDetails]

    # endpoints that can be accessed with admin permissions
    admin_endpoints: list[EndpointDetails]


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class ApiCommonTests(abc.ABC):
    @abc.abstractmethod
    def get_endpoints_configuration(self) -> ApiEndpointsRoles:
        """Retrieve the configuration for testing authentication of the endpoints.

        This method should be overridden by every concrete test class to provide
        the specific configuration required for testing authentication.

        Returns:
            ApiEndpointsRoles: The configuration containing roles and associated endpoints.
        """
        pass

    def pytest_generate_tests(self, metafunc):
        if "user_endpoint" in metafunc.fixturenames:
            metafunc.parametrize(
                "user_endpoint",
                self.get_endpoints_configuration().user_endpoints,
            )
        if "admin_endpoint" in metafunc.fixturenames:
            metafunc.parametrize(
                "admin_endpoint",
                self.get_endpoints_configuration().admin_endpoints,
            )

    async def test_user_endpoints_forbidden(
        self, user_endpoint: EndpointDetails, api_client: AsyncClient
    ):
        response = await api_client.request(
            user_endpoint.method, user_endpoint.path
        )
        assert response.status_code == 401

    async def test_admin_endpoints_forbidden(
        self,
        admin_endpoint: EndpointDetails,
        api_client: AsyncClient,
        authenticated_user_api_client_v3: AsyncClient,
    ):
        response = await api_client.request(
            admin_endpoint.method, admin_endpoint.path
        )
        assert response.status_code == 401

        response = await authenticated_user_api_client_v3.request(
            admin_endpoint.method, admin_endpoint.path
        )
        assert response.status_code == 403
