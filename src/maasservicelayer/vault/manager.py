#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import timedelta
from functools import lru_cache
from typing import Any

import structlog

from maasserver.config import RegionConfiguration
from maasservicelayer.utils.date import utcnow
from maasservicelayer.vault.api.apiclient import AsyncVaultApiClient
from maasservicelayer.vault.api.models.requests import (
    AppRoleLoginRequest,
    KvV2WriteRequest,
)

TOKEN_BEFORE_EXPIRY_LIMIT = timedelta(seconds=20)
APPROLE = "approle"

logger = structlog.getLogger()


class AsyncVaultManager:
    def __init__(
        self,
        vault_api_client: AsyncVaultApiClient,
        role_id: str,
        secret_id: str,
        secrets_base_path: str,
        secrets_mount: str = "secret",
    ):
        """
        Initializes a new instance of the AsyncVaultManager.

        Args:
            vault_api_client (AsyncVaultApiClient): The asynchronous Vault API client instance.
            role_id (str): The role ID used for authentication.
            secret_id (str): The secret ID used for authentication.
            secrets_base_path (str): The base path for secrets within the Vault.
            secrets_mount (str, optional): The mount point of the secrets engine within Vault. Defaults to "secret".

        Raises:
            ValueError: If role_id, secret_id, or secrets_base_path are empty strings.

        """
        self._role_id = role_id
        self._secret_id = secret_id
        self._secrets_base_path = secrets_base_path
        self._secrets_mount = secrets_mount
        self._cached_token = None
        self._cached_token_expire_time = None
        self._vault_api_client = vault_api_client

    async def get_valid_token(self, force: bool = False) -> str:
        """
        Retrieves and caches an access token for the Vault server. If the cached token has expired, then a new one is retrieved
        and cached.

        Args:
            force (bool, optional): Whether to force a token refresh regardless of its expiration status. Defaults to False.

        Returns:
            str: A valid Vault token.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultException: If there is any other error with Vault.
        """
        if force or self._is_token_expired():
            request = AppRoleLoginRequest(
                role_id=self._role_id,
                secret_id=self._secret_id,
            )
            login_response = await self._vault_api_client.auth_approle_login(
                approle=APPROLE, request=request
            )
            token_lookup_response = (
                await self._vault_api_client.token_lookup_self(
                    headers=AsyncVaultApiClient.build_headers_with_token(
                        login_response.auth.client_token
                    )
                )
            )
            self._cached_token = login_response.auth.client_token
            self._cached_token_expire_time = (
                token_lookup_response.data.expire_time
            )
            logger.debug("New vault access token has been cached")
        assert self._cached_token is not None
        return self._cached_token

    async def set(self, path: str, value: dict[str, Any]) -> None:
        """
        Sets a secret at the specified path in the KV V2 secrets engine.

        Args:
            path (str): The location where the secret should be stored.
            value (dict[str, Any]): The secret data to store.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error with Vault.
        """
        token = await self.get_valid_token()
        await self._vault_api_client.kv_v2_create_or_update(
            path=self._secret_path(path),
            kv_v2_mount_path=self._secrets_mount,
            request=KvV2WriteRequest(data=value),
            headers=AsyncVaultApiClient.build_headers_with_token(token),
        )

    async def get(self, path: str) -> dict[str, Any]:
        """
        Retrieves a secret from the specified path in the KV V2 secrets engine.

        Args:
            path (str): The location of the secret to retrieve.

        Returns:
            dict[str, Any]: The secret data retrieved from the specified path.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error with Vault.
        """
        token = await self.get_valid_token()
        response = await self._vault_api_client.kv_v2_read(
            path=self._secret_path(path),
            kv_v2_mount_path=self._secrets_mount,
            headers=AsyncVaultApiClient.build_headers_with_token(token),
        )
        return response.data.data

    async def delete(self, path: str) -> None:
        """
        Deletes a secret from the specified path in the KV V2 secrets engine.

        Args:
            path (str): The location of the secret to delete.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error with Vault.
        """
        token = await self.get_valid_token()
        await self._vault_api_client.kv_v2_delete_metadata_and_all_versions(
            path=self._secret_path(path),
            kv_v2_mount_path=self._secrets_mount,
            headers=AsyncVaultApiClient.build_headers_with_token(token),
        )

    def _is_token_expired(self) -> bool:
        has_expired = not self._cached_token or (
            self._cached_token_expire_time is not None
            and self._cached_token_expire_time
            <= (utcnow() - TOKEN_BEFORE_EXPIRY_LIMIT)
        )
        logger.debug("Vault access token was not set or has expired.")
        return has_expired

    def _secret_path(self, path: str) -> str:
        return f"{self._secrets_base_path}/{path}"


@lru_cache()
def get_region_vault_manager() -> AsyncVaultManager | None:
    """Return an AsyncVaultManager properly configured according to the region configuration.

    If configuration options for Vault are not set, None is returned.
    """
    with RegionConfiguration.open() as config:
        if not all(
            (config.vault_url, config.vault_approle_id, config.vault_secret_id)
        ):
            return None
        return AsyncVaultManager(
            vault_api_client=AsyncVaultApiClient(base_url=config.vault_url),  # type: ignore
            role_id=config.vault_approle_id,  # type: ignore
            secret_id=config.vault_secret_id,  # type: ignore
            secrets_base_path=config.vault_secrets_path,  # type: ignore
            secrets_mount=config.vault_secrets_mount,  # type: ignore
        )
