# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
from typing import Any

import httpx

from apiclient.maas_client import MAASOAuth
from maascommon.worker import worker_socket_paths

# httpx defaults to 5 seconds, which is too short for slow region API calls
# (e.g. rendering DHCP configuration on large deployments).
UNIX_CLIENT_TIMEOUT_SECONDS = 90


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
        return httpx.AsyncClient(
            transport=transport,
            headers=headers,
            timeout=httpx.Timeout(UNIX_CLIENT_TIMEOUT_SECONDS),
        )

    def _create_client(
        self, http_proxy: str | None, headers: dict[str, str]
    ) -> httpx.AsyncClient:
        if self.user_agent:
            headers["User-Agent"] = self.user_agent

        if http_proxy == "":
            # It might be that the http_proxy configuration is empty string, and it would crash httpx. Replace with None to
            # represent that the proxy is not set.
            http_proxy = None

        return httpx.AsyncClient(
            verify=False,
            proxy=http_proxy,
            timeout=httpx.Timeout(60 * 60, read=120),
            headers=headers,
        )

    @property
    def unix_client(self) -> httpx.AsyncClient:
        return self._unix_client

    def make_client(
        self, http_proxy: str | None, headers: dict[str, str] | None = None
    ) -> httpx.AsyncClient:
        return self._create_client(http_proxy, headers or {})

    async def request_async(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ):
        headers = {}
        self._oauth.sign_request(url, headers)
        # The UNIX socket serves plain HTTP. An https maas_url (e.g. MAAS
        # behind a TLS proxy) would otherwise start a TLS handshake on it.
        socket_url = httpx.URL(url).copy_with(scheme="http")
        response = await self.unix_client.request(
            method,
            socket_url,
            params=params,
            data=data,
            headers=headers,
        )
        response.raise_for_status()
        return response.json()
