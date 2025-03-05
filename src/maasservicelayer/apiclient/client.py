#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import ssl
from typing import Any
from urllib.parse import urljoin

from aiohttp import ClientSession, TCPConnector
from oauthlib import oauth1

from maascommon.constants import SYSTEM_CA_FILE


class APIClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        key, token, secret = api_key.split(":")
        self._oauth = oauth1.Client(
            key,
            resource_owner_key=token,
            resource_owner_secret=secret,
            signature_method=oauth1.SIGNATURE_PLAINTEXT,
        )

        self._session = ClientSession(
            connector=TCPConnector(
                ssl=ssl.create_default_context(cafile=SYSTEM_CA_FILE)
            ),
        )

    async def request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ):
        url = urljoin(str(self.base_url), path)
        _, headers, _ = self._oauth.sign(url)

        async with self._session.request(
            method,
            url,
            data=data,
            params=params,
            headers=headers,
        ) as response:
            response.raise_for_status()
            return await response.json()

    async def close(self):
        await self._session.close()
