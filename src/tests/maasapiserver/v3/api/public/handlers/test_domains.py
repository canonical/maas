#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.domains import DomainRequest
from maasapiserver.v3.api.public.models.responses.domains import (
    DomainResponse,
    DomainsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.domains import Domain
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.domains import DomainsService
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

DEFAULT_DOMAIN = Domain(
    authoritative=True,
    name="DEFAULT_DOMAIN_NAME",
    id=1,
)
TEST_DOMAIN = Domain(
    authoritative=False,
    name="test_domain",
    id=4,
)


class TestDomainsApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/domains"
    DEFAULT_DOMAIN_PATH = f"{BASE_PATH}/1"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/2"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/2"),
        ]

    async def test_list_domains_one_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.list.return_value = ListResult[Domain](
            items=[DEFAULT_DOMAIN, TEST_DOMAIN], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=2")
        assert response.status_code == 200
        domains_response = DomainsListResponse(**response.json())
        assert len(domains_response.items) == 2
        assert domains_response.total == 2
        assert domains_response.next is None

    async def test_list_domains_with_next_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.list.return_value = ListResult[Domain](
            items=[TEST_DOMAIN], total=2
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}?size=1")
        assert response.status_code == 200
        domains_response = DomainsListResponse(**response.json())
        assert len(domains_response.items) == 1
        assert domains_response.total == 2
        assert domains_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_get_by_id_get_default(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.get_by_id.return_value = DEFAULT_DOMAIN
        response = await mocked_api_client_user.get(self.DEFAULT_DOMAIN_PATH)
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        domain_response = DomainResponse(**response.json())
        assert domain_response.id == 1
        assert domain_response.name == "DEFAULT_DOMAIN_NAME"
        assert domain_response.authoritative is True

    async def test_get_by_id(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.get_by_id.return_value = TEST_DOMAIN
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/4")
        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        domain_response = DomainResponse(**response.json())
        assert domain_response.id == 4
        assert domain_response.name == "test_domain"
        assert domain_response.authoritative is False

    async def test_get_by_id_nonexist_id_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.get_by_id.return_value = None
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/100")
        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

    async def test_get_by_id_incorrect_id_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.get_by_id.side_effect = RequestValidationError(
            errors=[]
        )
        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/xyz")
        assert response.status_code == 422
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_post_valid_domain_401(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        domain_request = DomainRequest(
            name=TEST_DOMAIN.name, authoritative=TEST_DOMAIN.authoritative
        )
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.create.return_value = TEST_DOMAIN
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(domain_request)
        )
        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0
        domain_response = DomainResponse(**response.json())
        assert domain_response.id > 1
        assert domain_response.name == domain_request.name
        assert domain_response.authoritative == domain_request.authoritative
        assert (
            domain_response.hal_links.self.href
            == f"{self.BASE_PATH}/{domain_response.id}"
        )

    async def test_post_duplicate_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        domain_request = DomainRequest(name="domain")
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.create.side_effect = [
            TEST_DOMAIN,
            AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exists.",
                    )
                ]
            ),
        ]
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(domain_request)
        )

        assert response.status_code == 201
        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=jsonable_encoder(domain_request)
        )
        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 409
        assert len(error_response.details) == 1
        assert error_response.details[0].type == "UniqueConstraintViolation"
        assert "already exists" in error_response.details[0].message

    @pytest.mark.parametrize(
        "domain_request",
        [{"name": ""}, {"name": "$domain"}],
    )
    async def test_post_invalid_name_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
        domain_request: dict[str, str],
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.create.side_effect = ValueError(
            "Invalid domain name."
        )

        response = await mocked_api_client_admin.post(
            self.BASE_PATH, json=domain_request
        )
        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422

    async def test_delete_domain_with_id(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(f"{self.BASE_PATH}/10")
        assert response.status_code == 204

    async def test_delete_domain_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.delete_by_id.side_effect = None
        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/10",
            headers={"if-match": "my_etag"},
        )
        assert response.status_code == 204

    async def test_delete_domain_wrong_etag_error(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.domains = Mock(DomainsService)
        services_mock.domains.delete_by_id.side_effect = [
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
            f"{self.BASE_PATH}/10",
            headers={"if-match": "wrong_etag"},
        )
        assert response.status_code == 412
        error_response = ErrorBodyResponse(**response.json())
        assert error_response.code == 412
        assert error_response.message == "A precondition has failed."
        assert (
            error_response.details[0].type == ETAG_PRECONDITION_VIOLATION_TYPE
        )
