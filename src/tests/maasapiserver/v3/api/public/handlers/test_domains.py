#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.responses.domains import (
    DomainsListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
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
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

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
