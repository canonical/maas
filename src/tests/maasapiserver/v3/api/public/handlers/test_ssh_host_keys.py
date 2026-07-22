#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import AsyncClient
import pytest

from maasapiserver.v3.constants import V3_API_PREFIX
from maasservicelayer.exceptions.catalog import PreconditionFailedException
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.ssh_host_keys import TrustedSshHostKey
from maasservicelayer.services import ServiceCollectionV3
from tests.maasapiserver.v3.api.public.handlers.base import (
    ApiCommonTests,
    Endpoint,
)

TEST_KEY = TrustedSshHostKey(
    id=1,
    created=datetime(2026, 1, 1, tzinfo=timezone.utc),
    updated=datetime(2026, 1, 1, tzinfo=timezone.utc),
    host="192.168.1.1",
    key_type="ssh-rsa",
    public_key="AAAAB3NzaC1yc2EAAAADAQABAAABAQC0",
    label="rack-1",
)

TEST_KEY_2 = TrustedSshHostKey(
    id=2,
    created=datetime(2026, 1, 2, tzinfo=timezone.utc),
    updated=datetime(2026, 1, 2, tzinfo=timezone.utc),
    host="192.168.1.2",
    key_type="ecdsa-sha2-nistp256",
    public_key="AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTY",
    label="rack-2",
)


class TestSshHostKeysApi(ApiCommonTests):
    BASE_PATH = f"{V3_API_PREFIX}/ssh-host-keys"

    @pytest.fixture
    def user_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="GET", path=self.BASE_PATH),
            Endpoint(method="GET", path=f"{self.BASE_PATH}/1"),
        ]

    @pytest.fixture
    def admin_endpoints(self) -> list[Endpoint]:
        return [
            Endpoint(method="POST", path=self.BASE_PATH),
            Endpoint(method="DELETE", path=f"{self.BASE_PATH}/1"),
        ]

    async def test_list_ssh_host_keys(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.trusted_ssh_host_keys = AsyncMock()
        services_mock.trusted_ssh_host_keys.list.return_value = ListResult[
            TrustedSshHostKey
        ](items=[TEST_KEY], total=1)

        response = await mocked_api_client_user.get(self.BASE_PATH)
        assert response.status_code == 200
        body = response.json()
        assert len(body["items"]) == 1
        assert body["items"][0]["host"] == TEST_KEY.host
        assert body["items"][0]["key_type"] == TEST_KEY.key_type

    async def test_get_ssh_host_key(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.trusted_ssh_host_keys = AsyncMock()
        services_mock.trusted_ssh_host_keys.get_by_id.return_value = TEST_KEY

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/1")
        assert response.status_code == 200
        assert "ETag" in response.headers
        body = response.json()
        assert body["host"] == TEST_KEY.host
        assert body["public_key"] == TEST_KEY.public_key

    async def test_get_ssh_host_key_not_found(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_user: AsyncClient,
    ) -> None:
        services_mock.trusted_ssh_host_keys = AsyncMock()
        services_mock.trusted_ssh_host_keys.get_by_id.return_value = None

        response = await mocked_api_client_user.get(f"{self.BASE_PATH}/999")
        assert response.status_code == 404

    async def test_create_ssh_host_key(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.trusted_ssh_host_keys = AsyncMock()
        services_mock.trusted_ssh_host_keys.create.return_value = TEST_KEY

        response = await mocked_api_client_admin.post(
            self.BASE_PATH,
            json={
                "host": TEST_KEY.host,
                "key_type": TEST_KEY.key_type,
                "public_key": TEST_KEY.public_key,
                "label": TEST_KEY.label,
            },
        )
        assert response.status_code == 201
        assert "ETag" in response.headers
        body = response.json()
        assert body["host"] == TEST_KEY.host

    async def test_delete_ssh_host_key(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.trusted_ssh_host_keys = AsyncMock()
        services_mock.trusted_ssh_host_keys.delete_by_id.return_value = None

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"If-Match": TEST_KEY.etag()},
        )
        assert response.status_code == 204

    async def test_delete_ssh_host_key_precondition_failed(
        self,
        services_mock: ServiceCollectionV3,
        mocked_api_client_admin: AsyncClient,
    ) -> None:
        services_mock.trusted_ssh_host_keys = AsyncMock()
        services_mock.trusted_ssh_host_keys.delete_by_id.side_effect = (
            PreconditionFailedException()
        )

        response = await mocked_api_client_admin.delete(
            f"{self.BASE_PATH}/1",
            headers={"If-Match": "stale-etag"},
        )
        assert response.status_code == 412
