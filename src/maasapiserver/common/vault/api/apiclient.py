#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import ssl
from typing import Dict

from aiohttp import ClientResponse, ClientSession, TCPConnector

from maasapiserver.common.vault.api.models.exceptions import (
    VaultAuthenticationException,
    VaultException,
    VaultNotFoundException,
    VaultPermissionsException,
)
from maasapiserver.common.vault.api.models.requests import (
    AppRoleLoginRequest,
    KvV2WriteRequest,
)
from maasapiserver.common.vault.api.models.responses import (
    AppRoleLoginResponse,
    KvV2ReadResponse,
    KvV2WriteResponse,
    TokenLookupSelfResponse,
)


class AsyncVaultApiClient:
    def __init__(
        self,
        base_url: str,
    ):
        context = ssl.create_default_context()
        tcp_conn = TCPConnector(ssl=context)
        self._session = ClientSession(base_url=base_url, connector=tcp_conn)

    @classmethod
    def build_headers_with_token(cls, token: str) -> Dict[str, str]:
        """
        Constructs headers containing the Vault token.

        Args:
            token (str): The Vault token to include in the headers.

        Returns:
            Dict[str, str]: A dictionary containing the header with the Vault token.
        """
        return {"X-Vault-Token": token}

    async def auth_approle_login(
        self,
        approle: str,
        request: AppRoleLoginRequest,
        headers: Dict[str, str] | None = None,
    ) -> AppRoleLoginResponse:
        """
        Logs in using the AppRole authentication method.

        Args:
            approle (str): The approle name.
            request (AppRoleLoginRequest): The request object containing the role ID and secret ID.
            headers (Dict[str, str] | None, optional): Optional headers to include in the request. Defaults to None.

        Returns:
            AppRoleLoginResponse: An object containing the login response information.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error in the request.
        """
        response = await self._session.post(
            url=f"/v1/auth/{approle}/login",
            data=request.json(),
            headers=headers,
        )
        self._raise_for_status(response)
        return AppRoleLoginResponse.parse_obj(await response.json())

    async def token_lookup_self(
        self, headers: Dict[str, str] | None
    ) -> TokenLookupSelfResponse:
        """
        Performs a lookup of the calling client's token.

        Args:
            headers (Dict[str, str] | None): Optional headers to include in the request.

        Returns:
            TokenLookupSelfResponse: An object containing the token lookup information.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error in the request.
        """
        response = await self._session.get(
            url="/v1/auth/token/lookup-self",
            headers=headers,
        )
        self._raise_for_status(response)
        return TokenLookupSelfResponse.parse_obj(await response.json())

    async def kv_v2_delete_metadata_and_all_versions(
        self, path: str, kv_v2_mount_path: str, headers: Dict[str, str] | None
    ) -> None:
        """
        Deletes the metadata and all versions of a secret from a KV V2 secrets engine.

        Args:
            path (str): The location of the secret to delete.
            kv_v2_mount_path (str): The path where the KV V2 secrets engine is mounted.
            headers (Dict[str, str] | None): Optional headers to include in the request.

        Returns:
            None: This method returns None upon successful deletion.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error in the request.
        """
        response = await self._session.delete(
            url=f"/v1/{kv_v2_mount_path}/metadata/{path}",
            headers=headers,
        )
        self._raise_for_status(response)

    async def kv_v2_read(
        self, path: str, kv_v2_mount_path: str, headers: Dict[str, str] | None
    ) -> KvV2ReadResponse:
        """
        Reads the secret from a KV V2 secrets engine.

        Args:
            path (str): The location of the secret to read.
            kv_v2_mount_path (str): The path where the KV V2 secrets engine is mounted.
            headers (Dict[str, str] | None): Optional headers to include in the request.

        Returns:
            KvV2ReadResponse: An object containing the secret data.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error in the request.
        """
        response = await self._session.get(
            url=f"/v1/{kv_v2_mount_path}/data/{path}",
            headers=headers,
        )
        self._raise_for_status(response)
        return KvV2ReadResponse.parse_obj(await response.json())

    async def kv_v2_create_or_update(
        self,
        path: str,
        kv_v2_mount_path: str,
        request: KvV2WriteRequest,
        headers: Dict[str, str] | None,
    ) -> KvV2WriteResponse:
        """
        Creates or updates a secret in a KV V2 secrets engine.

        Args:
            path (str): The location of the secret to create or update.
            kv_v2_mount_path (str): The path where the KV V2 secrets engine is mounted.
            request (KvV2WriteRequest): The request object containing the secret data to be written.
            headers (Dict[str, str] | None): Optional headers to include in the request.

        Returns:
            KvV2WriteResponse: An object containing the response from the KV V2 secrets engine.

        Raises:
            VaultAuthenticationException: If there is an authentication error.
            VaultPermissionsException: If there is an authorization error.
            VaultNotFoundException: If the specified path for the secret is not found.
            VaultException: If there is any other error in the request.
        """
        response = await self._session.post(
            url=f"/v1/{kv_v2_mount_path}/data/{path}",
            data=request.json(),
            headers=headers,
        )
        self._raise_for_status(response)
        return KvV2WriteResponse.parse_obj(await response.json())

    def _raise_for_status(self, response: ClientResponse):
        if response.status < 400:
            return
        elif response.status == 401:
            raise VaultAuthenticationException(
                "The vault client returned 401. Please check the credentials."
            )
        elif response.status == 403:
            raise VaultPermissionsException(
                "The vault client returned 403. Please ensure you have the permissions to access "
                "this resource."
            )
        elif response.status == 404:
            raise VaultNotFoundException("The requested path was not found.")
        else:
            raise VaultException(
                f"The vault client returned {response.status}."
            )
