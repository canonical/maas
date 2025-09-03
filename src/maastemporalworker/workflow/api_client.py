# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from typing import Any

import httpx

from apiclient.maas_client import MAASOAuth
from maascommon.worker import worker_socket_paths


class MAASAPIClient:
    def __init__(self, url: str, token: str, user_agent: str = ""):
        self.url = url.rstrip("/")
        self.user_agent = user_agent
        self._oauth = MAASOAuth(*token.split(":"))
        self._unix_client = self._create_unix_client()

    def _create_unix_client(self) -> httpx.AsyncClient:
        # Calls to Region API over a UNIX socket.
        path = random.choice(worker_socket_paths())
        transport = httpx.AsyncHTTPTransport(uds=path)
        headers = {}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        return httpx.AsyncClient(transport=transport, headers=headers)

    def _create_client(self, http_proxy: str | None) -> httpx.AsyncClient:
        headers = {}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

        return httpx.AsyncClient(
            verify=False,
            proxy=http_proxy,
            timeout=httpx.Timeout(60 * 60, read=120),
            headers=headers,
        )

    @property
    def unix_client(self) -> httpx.AsyncClient:
        return self._unix_client

    def make_client(self, http_proxy: str | None) -> httpx.AsyncClient:
        return self._create_client(http_proxy)

    async def request_async(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ):
        headers = {}
        self._oauth.sign_request(url, headers)
        response = await self.unix_client.request(
            method,
            url,
            params=params,
            data=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
