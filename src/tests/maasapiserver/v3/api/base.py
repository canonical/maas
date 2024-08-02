import abc
from collections.abc import Coroutine, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, Type, TypeVar

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.common.models.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasapiserver.v3.api.models.responses.base import (
    HalResponse,
    TokenPaginatedResponse,
)
from maasapiserver.v3.auth.jwt import UserRole
from maasapiserver.v3.models.base import MaasTimestampedBaseModel
from tests.maasapiserver.fixtures.db import Fixture

T = TypeVar("T", bound=TokenPaginatedResponse)
M = TypeVar("M", bound=MaasTimestampedBaseModel)
R = TypeVar("R", bound=HalResponse)


@dataclass
class PaginatedEndpointTestConfig(Generic[M, T]):
    response_type: Type[T]
    create_resources_routine: Callable[..., Coroutine[Any, Any, Sequence[M]]]
    size_parameters: Iterable[int] = range(0, 10)

    def assert_routine(
        self, obj: M, list_response: T, href_base_path: str
    ) -> None:
        response_object = next(
            (o for o in list_response.items if o.id == obj.id)
        )
        assert obj.id == response_object.id
        assert obj.to_response(href_base_path) == response_object


@dataclass
class SingleResourceTestConfig(Generic[M, R]):
    response_type: Type[R]
    create_resource_routine: Callable[..., Coroutine[Any, Any, M]]

    def assert_routine(self, obj: M, response: R, href_base_path: str) -> None:
        assert obj.to_response(href_base_path) == response


@dataclass
class EndpointDetails:
    """
    Configuration class for testing an API endpoint.
    Attributes:
        method (str): The HTTP method to be used (e.g., GET, POST).
        path (str): The endpoint path, which may include format placeholders in the form {index.attr}.
                    Here, 'index' represents the index of the object and 'attr' represents the attribute
                    of the object to be used.
        user_role (UserRole): The user role required to access the endpoint.
        pagination_config (PaginatedEndpointTestConfig): Configuration for testing paginated endpoints.
        objects_factories (list): A list of factories for creating objects used in path parameters.
                                  They are executed like a pipeline so the output of the first is passed
                                  as an input to the second, and so on.
                                  Should accept two arguments: fixture and parent_object (optional).
        parent_object: Holds the last object created by the factories. This should not be initialized
                             manually.
    """

    method: str
    path: str
    user_role: UserRole
    resource_config: SingleResourceTestConfig | None = None
    # None if the endpoint does not support pagination
    pagination_config: PaginatedEndpointTestConfig | None = None
    objects_factories: (
        list[Callable[..., Coroutine[Any, Any, MaasTimestampedBaseModel]]]
        | None
    ) = None
    parent_object: MaasTimestampedBaseModel | None = field(
        init=False, default=None
    )

    async def build_path(self, fixture: Fixture):
        """
        Creates the objects necessary to build the path parameters using the
        supplied factories.
        Stores the last in `self.parent_object` for later use.
        """
        if self.objects_factories:
            parent_objects = []
            first_factory = self.objects_factories[0]
            parent_objects.append(await first_factory(fixture))
            for factory in self.objects_factories[1:]:
                parent_objects.append(
                    await factory(fixture, parent_objects[-1])
                )
            self.parent_object = parent_objects[-1]
            return self.path.format(*parent_objects)
        return self.path


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

        if metafunc.definition.originalname.startswith("test_single_resource"):
            resource_endpoints = list(
                filter(
                    lambda endpoint: endpoint.resource_config,
                    self.get_endpoints_configuration(),
                )
            )
            metafunc.parametrize("resource_endpoint", resource_endpoints)

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
        self,
        user_endpoint: EndpointDetails,
        api_client: AsyncClient,
        fixture: Fixture,
    ):
        path = await user_endpoint.build_path(fixture)
        response = await api_client.request(user_endpoint.method, path)
        assert response.status_code == 401

    async def test_admin_endpoints_forbidden(
        self,
        admin_endpoint: EndpointDetails,
        api_client: AsyncClient,
        authenticated_user_api_client_v3: AsyncClient,
        fixture: Fixture,
    ):
        path = await admin_endpoint.build_path(fixture)

        response = await api_client.request(admin_endpoint.method, path)
        assert response.status_code == 401

        response = await authenticated_user_api_client_v3.request(
            admin_endpoint.method, path
        )
        assert response.status_code == 403

    async def test_single_resource_get(
        self,
        resource_endpoint: EndpointDetails,
        authenticated_user_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        resource = (
            await resource_endpoint.resource_config.create_resource_routine(
                fixture
            )
        )
        base_path = await resource_endpoint.build_path(fixture)
        path = base_path + f"/{resource.id}"
        response = await authenticated_user_api_client_v3.get(path)
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        typed_response = resource_endpoint.resource_config.response_type(
            **response.json()
        )
        resource_endpoint.resource_config.assert_routine(
            resource, typed_response, base_path
        )

    async def test_single_resource_get_non_existent(
        self,
        resource_endpoint: EndpointDetails,
        authenticated_user_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        base_path = await resource_endpoint.build_path(fixture)
        path = base_path + "/999"
        response = await authenticated_user_api_client_v3.get(path)
        assert response.status_code == 404

        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_single_resource_get_malformed_request(
        self,
        resource_endpoint: EndpointDetails,
        authenticated_user_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        base_path = await resource_endpoint.build_path(fixture)
        path = base_path + "/xyz"
        response = await authenticated_user_api_client_v3.get(path)
        assert response.status_code == 422

        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_single_resource_delete(
        self,
        resource_endpoint: EndpointDetails,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        resource = (
            await resource_endpoint.resource_config.create_resource_routine(
                fixture
            )
        )
        base_path = await resource_endpoint.build_path(fixture)
        path = base_path + f"/{resource.id}"
        response = await authenticated_admin_api_client_v3.delete(path)
        assert response.status_code == 204
        check_response = await authenticated_admin_api_client_v3.get(path)
        assert check_response.status_code == 404

    async def test_single_resource_delete_non_existent(
        self,
        resource_endpoint: EndpointDetails,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        base_path = await resource_endpoint.build_path(fixture)
        path = base_path + "/999"
        response = await authenticated_admin_api_client_v3.delete(path)
        assert response.status_code == 204

    async def test_single_resource_delete_with_etag(
        self,
        resource_endpoint: EndpointDetails,
        authenticated_admin_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        resource = (
            await resource_endpoint.resource_config.create_resource_routine(
                fixture
            )
        )
        base_path = await resource_endpoint.build_path(fixture)
        path = base_path + f"/{resource.id}"
        failed_response = await authenticated_admin_api_client_v3.delete(
            path, headers={"if-match": "blabla"}
        )
        assert failed_response.status_code == 412
        error_response = ErrorBodyResponse(**failed_response.json())
        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )

        response = await authenticated_admin_api_client_v3.delete(
            path,
            headers={"if-match": resource.etag()},
        )
        assert response.status_code == 204
        check_response = await authenticated_admin_api_client_v3.get(path)
        assert check_response.status_code == 404

    async def test_pagination_endpoint_with_invalid_data(
        self,
        paginated_endpoint: EndpointDetails,
        token: str | None,
        size: int,
        authenticated_user_api_client_v3: AsyncClient,
        fixture: Fixture,
    ) -> None:
        path = await paginated_endpoint.build_path(fixture)
        response = await authenticated_user_api_client_v3.request(
            paginated_endpoint.method,
            f"{path}?token={token}&size={size}",
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

        path = await paginated_endpoint.build_path(fixture)
        if paginated_endpoint.parent_object:
            created_resources = await paginated_endpoint.pagination_config.create_resources_routine(
                fixture, size, paginated_endpoint.parent_object
            )
        else:
            created_resources = await paginated_endpoint.pagination_config.create_resources_routine(
                fixture, size
            )

        response = await api_client.request(paginated_endpoint.method, path)
        assert response.status_code == 200

        next_page_link = f"{path}?size=2"
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
                created_resources.pop(), typed_response, path
            )
            paginated_endpoint.pagination_config.assert_routine(
                created_resources.pop(), typed_response, path
            )
            next_page_link = typed_response.next
            if page == last_page:
                assert len(typed_response.items) == (size % 2 or 2)
                assert next_page_link is None
            else:
                assert len(typed_response.items) == 2
