#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from maasservicelayer.utils.date import utcnow
from maasservicelayer.vault.api.apiclient import AsyncVaultApiClient
from maasservicelayer.vault.api.models.exceptions import (
    VaultAuthenticationException,
)
from maasservicelayer.vault.api.models.requests import (
    AppRoleLoginRequest,
    KvV2WriteRequest,
)
from maasservicelayer.vault.api.models.responses import (
    AppRoleLoginDetailResponse,
    AppRoleLoginResponse,
    KvV2ReadDetailResponse,
    KvV2ReadResponse,
    KvV2WriteDetailResponse,
    KvV2WriteResponse,
    TokenLookupSelfDetailResponse,
    TokenLookupSelfResponse,
)
from maasservicelayer.vault.manager import AsyncVaultManager


def get_base_response_dict() -> dict[str, Any]:
    return {
        "request_id": "requestid",
        "lease_id": "leaseid",
        "renewable": False,
        "lease_duration": 0,
        "mount_type": "",
    }


def build_valid_login_response_stub(
    token: str | None = "token",
) -> AppRoleLoginResponse:
    return AppRoleLoginResponse(
        **get_base_response_dict(),
        auth=AppRoleLoginDetailResponse(
            client_token=token,
        )
    )


def build_valid_self_token_response_stub(
    expire_time: datetime | None = utcnow() + timedelta(minutes=30),
) -> TokenLookupSelfResponse:
    return TokenLookupSelfResponse(
        **get_base_response_dict(),
        data=TokenLookupSelfDetailResponse(
            issue_time=utcnow(),
            expire_time=expire_time,
        )
    )


@pytest.fixture
def async_vault_client_default_mock() -> AsyncVaultApiClient:
    apiclient = Mock(AsyncVaultApiClient)
    apiclient.auth_approle_login.return_value = (
        build_valid_login_response_stub()
    )
    apiclient.token_lookup_self.return_value = (
        build_valid_self_token_response_stub()
    )
    apiclient.kv_v2_delete_metadata_and_all_versions.return_value = None
    apiclient.kv_v2_create_or_update.return_value = KvV2WriteResponse(
        **get_base_response_dict(),
        data=KvV2WriteDetailResponse(created_time=utcnow(), version=1)
    )

    apiclient.kv_v2_read.return_value = KvV2ReadResponse(
        **get_base_response_dict(),
        data=KvV2ReadDetailResponse(data={"mykey": "myvalue"})
    )
    return apiclient


class TestAsyncVaultManager:
    @pytest.mark.asyncio
    async def test_get_valid_token_cache(
        self, async_vault_client_default_mock: Mock
    ) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        token = await manager.get_valid_token(force=False)
        assert token == "token"

        # Token is cached, meaning that the async vault client is not called anymore
        cached_token = await manager.get_valid_token(force=False)
        async_vault_client_default_mock.auth_approle_login.assert_awaited_once_with(
            approle="approle",
            request=AppRoleLoginRequest(
                role_id="role_id",
                secret_id="secret_id",
            ),
        )
        async_vault_client_default_mock.token_lookup_self.assert_awaited_once_with(
            headers=AsyncVaultApiClient.build_headers_with_token("token")
        )
        assert cached_token == "token"

    @pytest.mark.asyncio
    async def test_get_valid_token_is_forced_or_expired(
        self, async_vault_client_default_mock: Mock
    ) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        token = await manager.get_valid_token(force=False)
        assert token == "token"

        # Token is retrieved again if forced. Also, let's simulate that the retrieved token is also expired for the
        # sake of the next assertion
        async_vault_client_default_mock.auth_approle_login.return_value = (
            build_valid_login_response_stub(token="new_token")
        )
        async_vault_client_default_mock.token_lookup_self.return_value = (
            build_valid_self_token_response_stub(
                expire_time=utcnow() - timedelta(hours=1)
            )
        )
        new_token = await manager.get_valid_token(force=True)
        assert new_token == "new_token"

        # The manager will retrieve a new token because the current one has expired.
        async_vault_client_default_mock.auth_approle_login.return_value = (
            build_valid_login_response_stub(token="updated_token")
        )
        updated_token = await manager.get_valid_token(force=False)
        assert updated_token == "updated_token"

    @pytest.mark.asyncio
    async def test_get_valid_token_exception(
        self, async_vault_client_default_mock: Mock
    ) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        async_vault_client_default_mock.auth_approle_login.side_effect = (
            VaultAuthenticationException(message="Permission denied")
        )
        with pytest.raises(VaultAuthenticationException):
            await manager.get_valid_token()

    @pytest.mark.asyncio
    async def test_set(self, async_vault_client_default_mock: Mock) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        data = {"mykey": "myvalue"}
        await manager.set(path="mypath", value=data)
        # It should have retrieved a valid token
        async_vault_client_default_mock.auth_approle_login.assert_awaited_once()
        async_vault_client_default_mock.token_lookup_self.assert_awaited_once()

        # It should have called the async client to store the secret
        async_vault_client_default_mock.kv_v2_create_or_update.assert_awaited_once_with(
            path="base_path/mypath",
            kv_v2_mount_path="mount",
            request=KvV2WriteRequest(data=data),
            headers=AsyncVaultApiClient.build_headers_with_token("token"),
        )

    @pytest.mark.asyncio
    async def test_set_exception(
        self, async_vault_client_default_mock: Mock
    ) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        async_vault_client_default_mock.kv_v2_create_or_update.side_effect = (
            VaultAuthenticationException(message="Permission denied")
        )
        with pytest.raises(VaultAuthenticationException):
            data = {"mykey": "myvalue"}
            await manager.set(path="mypath", value=data)

    @pytest.mark.asyncio
    async def test_get(self, async_vault_client_default_mock: Mock) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        data = await manager.get(path="mypath")
        assert data == {"mykey": "myvalue"}
        # It should have retrieved a valid token
        async_vault_client_default_mock.auth_approle_login.assert_awaited_once()
        async_vault_client_default_mock.token_lookup_self.assert_awaited_once()

        # It should have called the async client to store the secret
        async_vault_client_default_mock.kv_v2_read.assert_awaited_once_with(
            path="base_path/mypath",
            kv_v2_mount_path="mount",
            headers=AsyncVaultApiClient.build_headers_with_token("token"),
        )

    @pytest.mark.asyncio
    async def test_get_exception(
        self, async_vault_client_default_mock: Mock
    ) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        async_vault_client_default_mock.kv_v2_read.side_effect = (
            VaultAuthenticationException(message="Permission denied")
        )
        with pytest.raises(VaultAuthenticationException):
            await manager.get(path="mypath")

    @pytest.mark.asyncio
    async def test_delete(self, async_vault_client_default_mock: Mock) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        await manager.delete(path="mypath")
        # It should have retrieved a valid token
        async_vault_client_default_mock.auth_approle_login.assert_awaited_once()
        async_vault_client_default_mock.token_lookup_self.assert_awaited_once()

        # It should have called the async client to store the secret
        async_vault_client_default_mock.kv_v2_delete_metadata_and_all_versions.assert_awaited_once_with(
            path="base_path/mypath",
            kv_v2_mount_path="mount",
            headers=AsyncVaultApiClient.build_headers_with_token("token"),
        )

    @pytest.mark.asyncio
    async def test_delete_exception(
        self, async_vault_client_default_mock: Mock
    ) -> None:
        manager = AsyncVaultManager(
            vault_api_client=async_vault_client_default_mock,
            role_id="role_id",
            secret_id="secret_id",
            secrets_base_path="base_path",
            secrets_mount="mount",
        )

        async_vault_client_default_mock.kv_v2_delete_metadata_and_all_versions.side_effect = VaultAuthenticationException(
            message="Permission denied"
        )
        with pytest.raises(VaultAuthenticationException):
            await manager.delete(path="mypath")
