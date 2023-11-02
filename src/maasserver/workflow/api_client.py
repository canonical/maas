import random
from typing import Any

from aiohttp import ClientSession, UnixConnector

from apiclient.maas_client import MAASOAuth
from maasserver.models.user import get_creds_tuple


class MAASAPIClient:
    def __init__(self, url: str, token):
        self.url = url.rstrip("/")
        self._oauth = MAASOAuth(*get_creds_tuple(token))

        # We run all activities on the same host as the Region.
        # We want to make calls to Region API over a UNIX socket.
        from maasserver.regiondservices.http import RegionHTTPService

        self._paths = RegionHTTPService.worker_socket_paths()

    async def request_async(
        self,
        method: str,
        url: str,
        params: dict[str, Any] = None,
        data: dict[str, Any] = None,
    ):
        path = random.choice(self._paths)
        conn = UnixConnector(path=path)

        headers = {
            "User-Agent": self.user_agent,
        }
        self._oauth.sign_request(url, headers)
        async with ClientSession(connector=conn, headers=headers) as session:
            async with session.request(
                method,
                url,
                verify_ssl=False,
                data=data,
                params=params,
            ) as response:
                response.raise_for_status()
                return await response.json()
