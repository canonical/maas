# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
import json
import os
import re
import shutil
import ssl
from typing import Self

from aiohttp import ClientResponseError, ClientSession
from aiohttp.client import TCPConnector

from maascommon.constants import SYSTEM_CA_FILE
from maasservicelayer.simplestreams.models import (
    SimpleStreamsIndexList,
    SimpleStreamsProductList,
    SimpleStreamsProductListFactory,
)

INDEX_REGEX = "streams/v1/.*[.](sjson|json)$"

SIGNED_INDEX_PATH = "streams/v1/index.sjson"

BEGIN_PGP_MESSAGE_HEADER = "-----BEGIN PGP SIGNED MESSAGE-----"
BEGIN_PGP_SIGNATURE_HEADER = "-----BEGIN PGP SIGNATURE-----"


class SimpleStreamsClientException(Exception):
    """Generic SimpleStreamsClient Exception."""


class SimpleStreamsClient:
    """Client to download data from a SimpleStreams Mirror.

    The preferred way of using it is through an async context manager. This will
    take care of closing the underlying `aiohttp.ClientSession`.
    Example:

        async with SimpleStreamsClient(
            url="http://ss-mirror.com",
            keyring_file="path/to/keyring",
        ) as client:
            product_list = await client.get_all_products()

    Attributes:
        url: The SimpleStreams mirror URL. If the URL ends with a path
            that matches 'streams/v1/.*[.](json|sjson)$', that index will be used.
            Otherwise, it defaults to 'streams/v1/index.sjson'.
        skip_pgp_verification: If True, skips PGP verification of the data.
        keyring_file: Path to the keyring file used for verifying signed data.
        http_proxy: Optional HTTP proxy to use when connecting to the mirror.

    Raises:
        SimpleStreamsClientException: the path to the keyring_file doesn't exist
            or no keyring_file was supplied but metadata must be PGP verified.
    """

    def __init__(
        self,
        url: str,
        skip_pgp_verification: bool = False,
        keyring_file: str | None = None,
        http_proxy: str | None = None,
    ):
        if keyring_file and not os.path.exists(keyring_file):
            raise SimpleStreamsClientException(
                f"The path to the keyring file '{keyring_file}' doesn't exists."
            )
        if keyring_file is None and skip_pgp_verification is False:
            raise SimpleStreamsClientException(
                "'keyring_file' cannot be None if pgp verification is enabled."
            )

        if match := re.search(INDEX_REGEX, url):
            self.url = url[: match.start()].removesuffix("/")
            self._index_path = url[match.start() :]
        else:
            self.url = url.removesuffix("/")
            self._index_path = SIGNED_INDEX_PATH

        self.http_proxy = http_proxy
        self._session = self._get_session()
        self.keyring_file = keyring_file
        self.skip_pgp_verification = skip_pgp_verification

    def _get_session(self) -> ClientSession:
        context = ssl.create_default_context(cafile=SYSTEM_CA_FILE)
        tcp_conn = TCPConnector(ssl=context)
        # TODO: set proxy on the session when we upgrade aiohttp to v3.11+
        return ClientSession(trust_env=True, connector=tcp_conn)

    async def _validate_pgp_signature(self, content: str):
        if shutil.which("gpgv"):
            cmd = ["gpgv", f"--keyring={self.keyring_file}", "-"]
        elif shutil.which("gpg"):
            cmd = ["gpg", "--verify", f"--keyring={self.keyring_file}", "-"]
        else:
            raise SimpleStreamsClientException(
                "Either 'gpg' or 'gpgv' command must be available."
            )
        sh = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await sh.communicate(input=content.encode())
        if sh.returncode != 0:
            raise SimpleStreamsClientException(
                f"Failed to verify PGP signature: {stderr}"
            )

    async def _parse_response(self, content: str) -> dict:
        """Parse and verify the response from the mirror.

        If PGP verification is enabled, the function will always attempt to validate
        the signature, even if the index file is unsigned. In such cases, it will
        fail and raise an error to alert the user that they are using an index
        file that is expected to be signed but isn't.
        """
        if not self.skip_pgp_verification:
            await self._validate_pgp_signature(content)
        if content.startswith(BEGIN_PGP_MESSAGE_HEADER):
            json_start = content.find("{")
            json_end = content.find(BEGIN_PGP_SIGNATURE_HEADER)
            content = content[json_start:json_end]
        return json.loads(content)

    async def http_get(self, url: str) -> dict:
        response = await self._session.get(url, proxy=self.http_proxy)
        try:
            response.raise_for_status()
        except ClientResponseError as e:
            raise SimpleStreamsClientException(
                f"Request to '{url}' failed: {e.status} {e.message}"
            ) from e
        raw_response = await response.text()
        return await self._parse_response(raw_response)

    async def get_index(self) -> SimpleStreamsIndexList:
        index_url = f"{self.url}/{self._index_path}"
        response = await self.http_get(index_url)
        return SimpleStreamsIndexList(**response)

    async def get_product(self, product_path: str) -> SimpleStreamsProductList:
        url = f"{self.url}/{product_path}"
        response = await self.http_get(url)
        return SimpleStreamsProductListFactory.produce(response)

    async def get_all_products(self) -> list[SimpleStreamsProductList]:
        index_list = await self.get_index()
        products = []
        for index in index_list.indexes:
            products.append(await self.get_product(index.path))
        return products

    async def close_session(self):
        await self._session.close()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_t, exc_v, exc_tb):
        await self.close_session()
