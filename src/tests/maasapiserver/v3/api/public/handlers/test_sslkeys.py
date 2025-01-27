#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi.encoders import jsonable_encoder
from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.requests.sslkeys import SSLKeyRequest
from maasapiserver.v3.api.public.models.responses.sslkey import (
    SSLKeyListResponse,
    SSLKeyResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sslkeys import SSLKeyClauseFactory
from maasservicelayer.exceptions.catalog import (
    AlreadyExistsException,
    BaseExceptionDetail,
    NotFoundException,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
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
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=f"{self.BASE_PATH}"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
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
            items=[SSLKEY_1], total=2
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=1",
        )

        assert response.status_code == 200
        sslkeys_response = SSLKeyListResponse(**response.json())
        assert len(sslkeys_response.items) == 1
        assert sslkeys_response.total == 2
        assert sslkeys_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_user_sslkeys_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.list.return_value = ListResult[SSLKey](
            items=[SSLKEY_1, SSLKEY_2], total=2
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=2",
        )

        assert response.status_code == 200
        sslkeys_response = SSLKeyListResponse(**response.json())
        assert len(sslkeys_response.items) == 2
        assert sslkeys_response.total == 2
        assert sslkeys_response.next is None

    # GET /users/me/sslkeys/{id}
    async def test_get_user_sslkey(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.get_one.return_value = SSLKEY_1

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{SSLKEY_1.id}"
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0

        sslkey_response = SSLKeyResponse(**response.json())

        assert sslkey_response.id == SSLKEY_1.id
        assert sslkey_response.key == SSLKEY_1.key

    async def test_get_user_sslkey_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        invalid_sslkey_id = 99

        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.get_one.return_value = None

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{invalid_sslkey_id}"
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 404

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

    # DELETE /users/me/sslkeys/{sslkey_id}
    async def test_delete_user_sslkey_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.delete_one.side_effect = None

        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/1",
        )

        assert response.status_code == 204

        services_mock.sslkeys.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=SSLKeyClauseFactory.and_clauses(
                    [
                        SSLKeyClauseFactory.with_id(1),
                        SSLKeyClauseFactory.with_user_id(0),
                    ]
                )
            ),
            etag_if_match=None,
        )

    async def test_delete_user_sslkey_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        sslkey_id_to_delete = 1
        wrong_etag = "wrong_tag"

        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.delete_one.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message=f"The resource etag '{wrong_etag}' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/{sslkey_id_to_delete}",
            headers={"if-match": wrong_etag},
        )

        assert response.status_code == 412

        services_mock.sslkeys.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=SSLKeyClauseFactory.and_clauses(
                    [
                        SSLKeyClauseFactory.with_id(sslkey_id_to_delete),
                        SSLKeyClauseFactory.with_user_id(0),
                    ]
                )
            ),
            etag_if_match=wrong_etag,
        )

    async def test_delete_user_sslkey_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        sslkey_id_to_delete = 99

        services_mock.sslkeys = Mock(SSLKeysService)
        services_mock.sslkeys.delete_one.side_effect = NotFoundException(
            details=[
                BaseExceptionDetail(
                    type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                    message=f"SSL key with id {sslkey_id_to_delete} does not exist.",
                )
            ]
        )

        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/{sslkey_id_to_delete}",
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

        error_response = ErrorBodyResponse(**response.json())

        assert error_response.kind == "Error"
        assert error_response.code == 404

        services_mock.sslkeys.delete_one.assert_called_once_with(
            query=QuerySpec(
                where=SSLKeyClauseFactory.and_clauses(
                    [
                        SSLKeyClauseFactory.with_id(sslkey_id_to_delete),
                        SSLKeyClauseFactory.with_user_id(0),
                    ]
                )
            ),
            etag_if_match=None,
        )
