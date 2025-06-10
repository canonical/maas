# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import random
import ssl
from typing import Any

from aiohttp import ClientSession, ClientTimeout, TCPConnector, UnixConnector

from apiclient.maas_client import MAASOAuth
from maascommon.constants import SYSTEM_CA_FILE
from maascommon.worker import worker_socket_paths


class MAASAPIClient:
    def __init__(self, url: str, token: str, user_agent: str = ""):
        self.url = url.rstrip("/")
        self.user_agent = user_agent
        self._oauth = MAASOAuth(*token.split(":"))
        self._unix_session = self._create_unix_session()
        self._session = self._create_session()

    def _create_unix_session(self) -> ClientSession:
        # We run all activities on the same host as the Region.
        # We want to make calls to Region API over a UNIX socket.
        path = random.choice(worker_socket_paths())
        conn = UnixConnector(path=path)
        headers = {}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        return ClientSession(connector=conn, headers=headers)

    def _create_session(self) -> ClientSession:
        headers = {}
        if self.user_agent:
            headers["User-Agent"] = self.user_agent
        timeout = ClientTimeout(total=60 * 60, sock_read=120)
        context = ssl.create_default_context(cafile=SYSTEM_CA_FILE)
        tcp_conn = TCPConnector(ssl=context)
        return ClientSession(
            trust_env=True,
            timeout=timeout,
            headers=headers,
            connector=tcp_conn,
        )

    @property
    def unix_session(self) -> ClientSession:
        return self._unix_session

    @property
    def session(self) -> ClientSession:
        return self._session

    async def request_async(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ):
        headers = {}
        self._oauth.sign_request(url, headers)
        async with self.unix_session.request(
            method,
            url,
            verify_ssl=False,
            data=data,
            params=params,
            headers=headers,
        ) as response:
            response.raise_for_status()
            return await response.json()
