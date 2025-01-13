#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.responses.sslkey import (
    SSLKeyListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.sslkey import SSLKeysService
from tests.fixtures import get_test_data_file
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

SSLKEY_1 = SSLKey(
    id=1,
    key=get_test_data_file("test_x509_0.pem"),
    user_id=1,
)
SSLKEY_2 = SSLKey(
    id=2,
    key=get_test_data_file("test_x509_1.pem"),
    user_id=1,
)


@pytest.mark.asyncio
class TestSSLKeysApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/users/me/sslkeys"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    # GET /users/me/sslkeys
    async def test_list_user_sslkeys_has_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.list.return_value = ListResult[SSLKey](
            items=[SSLKEY_1], next_token=str(SSLKEY_2.id)
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=1",
        )

        assert response.status_code == 200
        sslkeys_response = SSLKeyListResponse(**response.json())
        assert len(sslkeys_response.items) == 1
        assert (
            sslkeys_response.next
            == f"{self.BASE_PATH}?{TokenPaginationParams.to_href_format(token=str(SSLKEY_2.id), size='1')}"
        )

    async def test_list_user_sslkeys_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.list.return_value = ListResult[SSLKey](
            items=[SSLKEY_1, SSLKEY_2], next_token=None
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=2",
        )

        assert response.status_code == 200
        sslkeys_response = SSLKeyListResponse(**response.json())
        assert len(sslkeys_response.items) == 2
        assert sslkeys_response.next is None
