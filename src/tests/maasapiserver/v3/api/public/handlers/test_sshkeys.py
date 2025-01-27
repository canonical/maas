#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from httpx import AsyncClient
import pytest

from maasapiserver.common.api.models.responses.errors import ErrorBodyResponse
from maasapiserver.v3.api.public.models.responses.sshkeys import (
    SshKeyResponse,
    SshKeysListResponse,
)
from maasapiserver.v3.constants import V3_API_PREFIX
from maascommon.enums.sshkeys import SshKeysProtocolType
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.sshkeys import SshKeyClauseFactory
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    PreconditionFailedException,
)
from maasservicelayer.exceptions.constants import (
    ETAG_PRECONDITION_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.sshkeys import SshKey
from maasservicelayer.services import ServiceCollectionV3
from maasservicelayer.services.sshkeys import SshKeysService
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_ED25519_KEY = (
    "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBEqkw2AgmkjqNjCFuiKXeUgLNmRbgVr8"
    "W2TlAvFybJv ed255@bar"
)

SSHKEY_1 = SshKey(id=1, key=TEST_ED25519_KEY, user_id=1)

SSHKEY_2 = SshKey(
    id=1,
    key=TEST_ED25519_KEY,
    user_id=1,
    protocol=SshKeysProtocolType.LP,
    auth_id="foo",
)


class TestSshKeyApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/users/me/sshkeys"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=f"{self.BASE_PATH}"),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="POST", path=f"{self.BASE_PATH}:import"),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return []

    async def test_list_user_sshkeys_has_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.list.return_value = ListResult[SshKey](
            items=[SSHKEY_1], total=2
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=1",
        )

        assert response.status_code == 200
        sshkeys_response = SshKeysListResponse(**response.json())
        assert len(sshkeys_response.items) == 1
        assert sshkeys_response.next == f"{self.BASE_PATH}?page=2&size=1"

    async def test_list_user_sshkeys_no_other_page(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.list.return_value = ListResult[SshKey](
            items=[SSHKEY_1, SSHKEY_2], total=2
        )
        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}?size=2",
        )

        assert response.status_code == 200
        sshkeys_response = SshKeysListResponse(**response.json())
        assert len(sshkeys_response.items) == 2
        assert sshkeys_response.total == 2
        assert sshkeys_response.next is None

    async def test_get_200(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.get_one.return_value = SSHKEY_1

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{SSHKEY_1.id}",
        )

        assert response.status_code == 200
        assert len(response.headers["ETag"]) > 0
        assert response.json() == {
            "kind": "SshKey",
            "id": SSHKEY_1.id,
            "key": SSHKEY_1.key,
            "auth_id": SSHKEY_1.auth_id,
            "protocol": SSHKEY_1.protocol,
            # TODO: FastAPI response_model_exclude_none not working. We need to fix this before making the api public
            "_embedded": None,
            "_links": {"self": {"href": f"{self.BASE_PATH}/{SSHKEY_1.id}"}},
        }

    async def test_get_404(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.get_one.return_value = None

        response = await mocked_api_client_user.get(
            f"{self.BASE_PATH}/{SSHKEY_1.id}",
        )

        assert response.status_code == 404
        assert "ETag" not in response.headers

    async def test_create_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.create.return_value = SSHKEY_1

        sshkey_request = {"key": TEST_ED25519_KEY}

        response = await mocked_api_client_user.post(
            self.BASE_PATH, json=sshkey_request
        )

        assert response.status_code == 201
        assert "ETag" in response.headers

        sshkey_response = SshKeyResponse(**response.json())
        assert sshkey_response.key == SSHKEY_1.key
        assert sshkey_response.protocol == SSHKEY_1.protocol
        assert sshkey_response.auth_id == SSHKEY_1.auth_id

    async def test_import_201(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.import_keys.return_value = [SSHKEY_2]

        sshkey_request = {"protocol": "lp", "auth_id": "foo"}

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}:import", json=sshkey_request
        )

        assert response.status_code == 201

        sshkey_response = SshKeysListResponse(**response.json())
        assert len(sshkey_response.items) == 1
        assert sshkey_response.next is None

    @pytest.mark.parametrize(
        "protocol, auth_id, message",
        [
            ("lp", None, "none is not an allowed value"),
            (None, "foo", "none is not an allowed value"),
            (
                "wrong",
                "foo",
                "value is not a valid enumeration member; permitted: 'lp', 'gh'",
            ),
        ],
    )
    async def test_import_422(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
        protocol: str | None,
        auth_id: str | None,
        message: str,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.create.return_value = SSHKEY_1

        sshkey_request = {"protocol": protocol, "auth_id": auth_id}

        response = await mocked_api_client_user.post(
            f"{self.BASE_PATH}:import", json=sshkey_request
        )

        error_response = ErrorBodyResponse(**response.json())
        assert error_response.kind == "Error"
        assert error_response.code == 422
        assert error_response.details is not None
        assert error_response.details[0].message == message

    async def test_delete_204(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.get_one.return_value = SSHKEY_1
        services_mock.sshkeys.delete_by_id.return_value = SSHKEY_1

        response = await mocked_api_client_user.delete(f"{self.BASE_PATH}/1")
        assert response.status_code == 204

    async def test_delete_with_etag(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.sshkeys = Mock(SshKeysService)
        services_mock.sshkeys.get_one.return_value = SSHKEY_1
        services_mock.sshkeys.delete_by_id.side_effect = PreconditionFailedException(
            details=[
                BaseExceptionDetail(
                    type=ETAG_PRECONDITION_VIOLATION_TYPE,
                    message="The resource etag 'wrong_etag' did not match 'my_etag'.",
                )
            ]
        )

        response = await mocked_api_client_user.delete(
            f"{self.BASE_PATH}/1", headers={"if-match": "wrong_etag"}
        )
        assert response.status_code == 412
        services_mock.sshkeys.get_one.assert_called_with(
            query=QuerySpec(
                where=SshKeyClauseFactory.and_clauses(
                    [
                        SshKeyClauseFactory.with_id(1),
                        SshKeyClauseFactory.with_user_id(0),
                    ]
                )
            )
        )
        services_mock.sshkeys.delete_by_id.assert_called_with(
            SSHKEY_1.id,
            etag_if_match="wrong_etag",
        )
