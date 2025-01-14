#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.query import (
    TokenPaginationParams,
)
from maasapiserver.v3.api.public.models.requests.sslkeys import SSLKeyRequest
from maasapiserver.v3.api.public.models.responses.sslkey import (
    SSLKeyListResponse,
    SSLKeyResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
)
from maasservicelayer.exceptions.constants import (
    UNIQUE_CONSTRAINT_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.sslkeys import SSLKey
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.sslkey import SSLKeysService
from maasservicelayer.utils.date import utcnow
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
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
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

    # POST /users/me/sslkeys
    async def test_create_user_sslkey_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        now = utcnow()
        test_ssl_key = get_test_data_file("test_x509_0.pem")

        create_sslkey_request = SSLKeyRequest(
            key=test_ssl_key,
        )

        new_sslkey = SSLKey(
            id=0,
            key=test_ssl_key,
            created=now,
            updated=now,
            user_id=0,
        )

        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.create.return_value = new_sslkey

        response = await mocked_api_client_user.post(
            self.BASE_PATH,
            json=jsonable_encoder(create_sslkey_request),
        )

        assert response.status_code == 201
        assert len(response.headers["ETag"]) > 0

        sslkey_response = SSLKeyResponse(**response.json())

        assert sslkey_response.id == new_sslkey.id
        assert sslkey_response.key == new_sslkey.key

    async def test_create_user_sslkey_409(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        now = utcnow()
        test_ssl_key = get_test_data_file("test_x509_0.pem")

        create_sslkey_request = SSLKeyRequest(
            key=test_ssl_key,
        )

        new_sslkey = SSLKey(
            id=0,
            key=test_ssl_key,
            created=now,
            updated=now,
            user_id=0,
        )

        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.create.side_effect = [
            new_sslkey,
            AlreadyExistsException(
                details=[
                    BaseExceptionDetail(
                        type=UNIQUE_CONSTRAINT_VIOLATION_TYPE,
                        message="A resource with such identifiers already exist.",
                    )
                ],
            ),
        ]

        response = await mocked_api_client_user.post(
            self.BASE_PATH,
            json=jsonable_encoder(create_sslkey_request),
        )

        assert response.status_code == 201

        response = await mocked_api_client_user.post(
            self.BASE_PATH,
            json=jsonable_encoder(create_sslkey_request),
        )

        assert response.status_code == 409

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 409

    async def test_create_user_sslkey_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        new_sslkey_request = {"key": None}

        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.create.return_value = None

        response = await mocked_api_client_user.post(
            self.BASE_PATH,
            json=jsonable_encoder(new_sslkey_request),
        )

        assert response.status_code == 422

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 422
