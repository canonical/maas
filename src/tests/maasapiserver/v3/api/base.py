import abc
from dataclasses import dataclass
from typing import Callable, Generic, Type, TypeVar

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.models.responses.base import TokenPaginatedResponse
from maasapiserver.v3.auth.jwt import UserRole
from tests.maasapiserver.fixtures.db import Fixture

T = TypeVar("T", bound=TokenPaginatedResponse)


@dataclass
class PaginatedEndpointTestConfig(Generic[T]):
    response_type: Type[T]
    create_resources_routine: Callable
    assert_routine: Callable
    size_parameters: list[int] = range(0, 10)


@dataclass
class EndpointDetails:
    method: str
    path: str
    user_role: UserRole
    # None if the endpoint does not support pagination
    pagination_config: PaginatedEndpointTestConfig | None = None


@pytest.mark.usefixtures("ensuremaasdb")
@pytest.mark.asyncio
class ApiCommonTests(abc.ABC):
    INVALID_PAGINATION_TEST_DATA = [(None, 0), (None, -1), (None, 1001)]

    @abc.abstractmethod
    def get_endpoints_configuration(self) -> list[EndpointDetails]:
        """Retrieve the configuration for testing authentication and pagination of the endpoints.

        This method should be overridden by every concrete test class to provide
        the specific configuration required for testing authentication.

        Returns:
            list[EndpointDetails]: The list containing the endpoints configurations.
        """
        pass

    def pytest_generate_tests(self, metafunc):
        # generate dynamically the data for the parametrized tests
        if metafunc.definition.originalname == "test_user_endpoints_forbidden":
            metafunc.parametrize(
                "user_endpoint",
                list(
                    filter(
                        lambda endpoint: endpoint.user_role == UserRole.USER,
                        self.get_endpoints_configuration(),
                    )
                ),
            )
        if (
            metafunc.definition.originalname
            == "test_admin_endpoints_forbidden"
        ):
            metafunc.parametrize(
                "admin_endpoint",
                list(
                    filter(
                        lambda endpoint: endpoint.user_role == UserRole.ADMIN,
                        self.get_endpoints_configuration(),
                    )
                ),
            )
        if (
            metafunc.definition.originalname
            == "test_pagination_endpoint_with_invalid_data"
        ):
            paginated_endpoints = list(
                filter(
                    lambda endpoint: endpoint.pagination_config,
                    self.get_endpoints_configuration(),
                )
            )
            # for each endpoint
            metafunc.parametrize(
                "paginated_endpoint",
                paginated_endpoints,
            )
            # for each test data
            metafunc.parametrize(
                "token,size", self.INVALID_PAGINATION_TEST_DATA
            )
        if metafunc.definition.originalname == "test_pagination_parameters":
            paginated_endpoints = list(
                filter(
                    lambda endpoint: endpoint.pagination_config,
                    self.get_endpoints_configuration(),
                )
            )
            metafunc.parametrize(
                "paginated_endpoint,size",
                [
                    (endpoint, size)
                    for endpoint in paginated_endpoints
                    for size in endpoint.pagination_config.size_parameters
                ],
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

    async def test_pagination_endpoint_with_invalid_data(
        self,
        paginated_endpoint: EndpointDetails,
        token: str | None,
        size: int,
        authenticated_user_api_client_v3: AsyncClient,
    ) -> None:
        response = await authenticated_user_api_client_v3.request(
            paginated_endpoint.method,
            f"{paginated_endpoint.path}?token={token}&size={size}",
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_pagination_parameters(
        self,
        paginated_endpoint: EndpointDetails,
        size: int,
        api_client: AsyncClient,
        authenticated_user_api_client_v3: AsyncClient,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        # set the required client according to the endpoint requirements
        if paginated_endpoint.user_role == UserRole.USER:
            api_client = authenticated_user_api_client_v3
        if paginated_endpoint.user_role == UserRole.ADMIN:
            api_client = authenticated_admin_api_client_v3

        created_resources = await paginated_endpoint.pagination_config.create_resources_routine(
            fixture, size
        )

        response = await api_client.request(
            paginated_endpoint.method, paginated_endpoint.path
        )
        assert response.status_code == 200

        next_page_link = f"{paginated_endpoint.path}?size=2"
        last_page = size // 2
        for page in range(last_page):
            response = await api_client.request(
                paginated_endpoint.method,
                next_page_link,
            )
            assert response.status_code == 200
            typed_response = (
                paginated_endpoint.pagination_config.response_type(
                    **response.json()
                )
            )
            paginated_endpoint.pagination_config.assert_routine(
                created_resources.pop(), typed_response
            )
            paginated_endpoint.pagination_config.assert_routine(
                created_resources.pop(), typed_response
            )
            next_page_link = typed_response.next
            if page == last_page:
                assert len(typed_response.items) == (size % 2 or 2)
                assert next_page_link is None
            else:
                assert len(typed_response.items) == 2
