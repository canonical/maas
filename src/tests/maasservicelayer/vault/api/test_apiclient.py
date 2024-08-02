#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

import pytest

from maasservicelayer.vault.api.apiclient import AsyncVaultApiClient
from maasservicelayer.vault.api.models.exceptions import (
    VaultAuthenticationException,
    VaultException,
    VaultNotFoundException,
    VaultPermissionsException,
)
from maasservicelayer.vault.api.models.requests import (
    AppRoleLoginRequest,
    KvV2WriteRequest,
)
from maasservicelayer.vault.api.models.responses import (
    AppRoleLoginResponse,
    KvV2ReadResponse,
    KvV2WriteResponse,
    TokenLookupSelfResponse,
)


class TestAsyncVaultApiClient:
    @pytest.mark.asyncio
    async def test_auth_approle_login_200(self, mock_aioresponse) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {
            "request_id": "0fd03624-eea4-6122-e995-601e2076c7f0",
            "lease_id": "",
            "renewable": False,
            "lease_duration": 0,
            "data": None,
            "wrap_info": None,
            "warnings": None,
            "auth": {
                "client_token": "mytoken",
                "accessor": "",
                "policies": ["default"],
                "token_policies": ["default"],
                "metadata": {"role_name": "my-role"},
                "lease_duration": 2764800,
                "renewable": False,
                "entity_id": "684fb4ca-7aec-e8f3-1183-23267b2bbcbf",
                "token_type": "batch",
                "orphan": True,
                "mfa_requirement": None,
                "num_uses": 0,
            },
            "mount_type": "",
        }
        mock_aioresponse.post(
            "/v1/auth/approle/login", status=200, payload=expected_response
        )

        request = AppRoleLoginRequest(role_id="role_id", secret_id="secret_id")
        response = await client.auth_approle_login("approle", request=request)
        assert response == AppRoleLoginResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_with(
            url="/v1/auth/approle/login",
            data='{"role_id": "role_id", "secret_id": "secret_id"}',
            headers=None,
            allow_redirects=True,
            method="POST",
        )

    @pytest.mark.parametrize(
        "status, exception",
        [
            (401, VaultAuthenticationException),
            (403, VaultPermissionsException),
            (404, VaultNotFoundException),
            (500, VaultException),
        ],
    )
    @pytest.mark.asyncio
    async def test_auth_approle_login_error(
        self, status, exception, mock_aioresponse
    ) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {"errors": ["permission denied"]}
        mock_aioresponse.post(
            "/v1/auth/approle/login", status=status, payload=expected_response
        )

        request = AppRoleLoginRequest(role_id="wrong", secret_id="wrong")
        with pytest.raises(exception):
            await client.auth_approle_login("approle", request=request)

    @pytest.mark.asyncio
    async def test_token_lookup_self_200(self, mock_aioresponse) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {
            "request_id": "80eb377c-77d8-842c-8fb2-02baa2e952ff",
            "lease_id": "",
            "renewable": False,
            "lease_duration": 0,
            "data": {
                "accessor": "",
                "creation_time": 1717160589,
                "creation_ttl": 2764800,
                "display_name": "approle",
                "entity_id": "684fb4ca-7aec-e8f3-1183-23267b2bbcbf",
                "expire_time": "2024-07-02T13:03:09Z",
                "explicit_max_ttl": 0,
                "id": "myid",
                "issue_time": "2024-05-31T13:03:09Z",
                "meta": {"role_name": "my-role"},
                "num_uses": 0,
                "orphan": True,
                "path": "auth/approle/login",
                "policies": ["default"],
                "renewable": False,
                "ttl": 2764799,
                "type": "batch",
            },
            "wrap_info": None,
            "warnings": None,
            "auth": None,
            "mount_type": "token",
        }
        mock_aioresponse.get(
            "/v1/auth/token/lookup-self", status=200, payload=expected_response
        )

        headers = {"X-Vault-Token": "mytoken"}
        response = await client.token_lookup_self(headers=headers)
        assert response == TokenLookupSelfResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_with(
            url="/v1/auth/token/lookup-self",
            headers=headers,
            allow_redirects=True,
            method="GET",
        )

    @pytest.mark.parametrize(
        "status, exception",
        [
            (401, VaultAuthenticationException),
            (403, VaultPermissionsException),
            (404, VaultNotFoundException),
            (500, VaultException),
        ],
    )
    @pytest.mark.asyncio
    async def test_token_lookup_self_error(
        self, status: int, exception: Type[Exception], mock_aioresponse
    ) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {"errors": ["permission denied"]}

        mock_aioresponse.get(
            "/v1/auth/token/lookup-self",
            status=status,
            payload=expected_response,
        )

        headers = {"X-Vault-Token": "wrong"}
        with pytest.raises(exception):
            await client.token_lookup_self(headers=headers)

    @pytest.mark.asyncio
    async def test_kv_v2_delete_metadata_and_all_versions_204(
        self, mock_aioresponse
    ) -> None:
        # Note that vault returns 204 also in the case the secret does not exist.

        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = None
        mock_aioresponse.delete(
            "/v1/secret/metadata/test/dummy",
            status=204,
            payload=expected_response,
        )

        headers = {"X-Vault-Token": "mytoken"}
        response = await client.kv_v2_delete_metadata_and_all_versions(
            path="test/dummy", kv_v2_mount_path="secret", headers=headers
        )
        assert response is None
        mock_aioresponse.assert_called_with(
            url="/v1/secret/metadata/test/dummy",
            headers=headers,
            allow_redirects=True,
            method="DELETE",
        )

    @pytest.mark.parametrize(
        "status, exception",
        [
            (401, VaultAuthenticationException),
            (403, VaultPermissionsException),
            (404, VaultNotFoundException),
            (500, VaultException),
        ],
    )
    @pytest.mark.asyncio
    async def test_kv_v2_delete_metadata_and_all_versions_error(
        self, status: int, exception: Type[Exception], mock_aioresponse
    ) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = None

        mock_aioresponse.delete(
            "/v1/secret/metadata/test/dummy",
            status=status,
            payload=expected_response,
        )

        headers = {"X-Vault-Token": "mytoken"}
        with pytest.raises(exception):
            await client.kv_v2_delete_metadata_and_all_versions(
                path="test/dummy", kv_v2_mount_path="secret", headers=headers
            )

    @pytest.mark.asyncio
    async def test_kv_v2_read_200(self, mock_aioresponse) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {
            "request_id": "ef593bcc-164b-450a-a1b2-bbac9e376c41",
            "lease_id": "",
            "renewable": False,
            "lease_duration": 0,
            "data": {
                "data": {"test": "ciao"},
                "metadata": {
                    "created_time": "2024-05-31T13:17:52.858732629Z",
                    "custom_metadata": None,
                    "deletion_time": "",
                    "destroyed": False,
                    "version": 5,
                },
            },
            "wrap_info": None,
            "warnings": None,
            "auth": None,
            "mount_type": "kv",
        }
        mock_aioresponse.get(
            "/v1/secret/data/test/dummy", status=200, payload=expected_response
        )

        headers = {"X-Vault-Token": "mytoken"}
        response = await client.kv_v2_read(
            path="test/dummy", kv_v2_mount_path="secret", headers=headers
        )
        assert response == KvV2ReadResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_with(
            url="/v1/secret/data/test/dummy",
            headers=headers,
            allow_redirects=True,
            method="GET",
        )

    @pytest.mark.parametrize(
        "status, exception",
        [
            (401, VaultAuthenticationException),
            (403, VaultPermissionsException),
            (404, VaultNotFoundException),
            (500, VaultException),
        ],
    )
    @pytest.mark.asyncio
    async def test_kv_v2_read_error(
        self, status, exception, mock_aioresponse
    ) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {"errors": []}

        mock_aioresponse.get(
            "/v1/secret/data/test/dummy",
            status=status,
            payload=expected_response,
        )

        headers = {"X-Vault-Token": "mytoken"}
        with pytest.raises(exception):
            await client.kv_v2_read(
                path="test/dummy", kv_v2_mount_path="secret", headers=headers
            )

    @pytest.mark.asyncio
    async def test_kv_v2_create_or_update_200(self, mock_aioresponse) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {
            "request_id": "25faea97-c530-5db5-632f-99e101458b21",
            "lease_id": "",
            "renewable": False,
            "lease_duration": 0,
            "data": {
                "created_time": "2024-05-31T13:22:58.379524346Z",
                "custom_metadata": None,
                "deletion_time": "",
                "destroyed": False,
                "version": 3,
            },
            "wrap_info": None,
            "warnings": None,
            "auth": None,
            "mount_type": "kv",
        }
        mock_aioresponse.post(
            "/v1/secret/data/test/dummy", status=200, payload=expected_response
        )

        headers = {"X-Vault-Token": "mytoken"}
        response = await client.kv_v2_create_or_update(
            path="test/dummy",
            kv_v2_mount_path="secret",
            request=KvV2WriteRequest(data={"test_key": "test_value"}),
            headers=headers,
        )
        assert response == KvV2WriteResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_with(
            url="/v1/secret/data/test/dummy",
            data='{"options": null, "data": {"test_key": "test_value"}}',
            headers=headers,
            allow_redirects=True,
            method="POST",
        )

    @pytest.mark.parametrize(
        "status, exception",
        [
            (401, VaultAuthenticationException),
            (403, VaultPermissionsException),
            (404, VaultNotFoundException),
            (500, VaultException),
        ],
    )
    @pytest.mark.asyncio
    async def test_kv_v2_create_or_update_error(
        self, status, exception, mock_aioresponse
    ) -> None:
        client = AsyncVaultApiClient(base_url="http://test:5200/")
        expected_response = {"errors": []}

        mock_aioresponse.post(
            "/v1/secret/data/test/dummy",
            status=status,
            payload=expected_response,
        )

        headers = {"X-Vault-Token": "wrong"}
        with pytest.raises(exception):
            await client.kv_v2_create_or_update(
                "test/dummy",
                "secret",
                request=KvV2WriteRequest(data={"test_key": "test_value"}),
                headers=headers,
            )
