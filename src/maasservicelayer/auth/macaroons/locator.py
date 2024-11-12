#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import ssl
from urllib.parse import urlparse

from aiohttp import ClientSession, CookieJar, TCPConnector
from macaroonbakery import bakery
from macaroonbakery.httpbakery import BAKERY_PROTOCOL_HEADER, ThirdPartyLocator

from maascommon.constants import SYSTEM_CA_FILE


class AsyncThirdPartyLocator(ThirdPartyLocator):
    """Implements macaroonbakery.ThirdPartyLocator by first looking in the
    backing cache and, if that fails, making an HTTP request to find the
    information associated with the given discharge location.

    This is the async porting of ThirdPartyLocator with no extra logic.
    """

    BAKERY_HEADERS = {BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION)}

    def __init__(self, allow_insecure=False):
        """
        @param url: the url to retrieve public_key
        @param allow_insecure: By default it refuses to use insecure URLs.
        """
        super().__init__(allow_insecure=allow_insecure)
        context = ssl.create_default_context(cafile=SYSTEM_CA_FILE)
        tcp_conn = TCPConnector(ssl=context)
        self._session = ClientSession(
            headers=self.BAKERY_HEADERS,
            trust_env=True,
            cookie_jar=CookieJar(unsafe=True),
            connector=tcp_conn,
        )

    async def third_party_info(self, loc):
        u = urlparse(loc)
        if u.scheme != "https" and not self._allow_insecure:
            raise bakery.ThirdPartyInfoNotFound(
                "untrusted discharge URL {}".format(loc)
            )
        loc = loc.rstrip("/")
        info = self._cache.get(loc)
        if info is not None:
            return info
        url_endpoint = "/discharge/info"
        resp = await self._session.get(url=loc + url_endpoint)
        status_code = resp.status
        if status_code == 404:
            url_endpoint = "/publickey"
            resp = await self._session.get(url=loc + url_endpoint)
            status_code = resp.status
        if status_code != 200:
            raise bakery.ThirdPartyInfoNotFound(
                "unable to get info from {}".format(url_endpoint)
            )
        json_resp = await resp.json()
        if json_resp is None:
            raise bakery.ThirdPartyInfoNotFound(
                "no response from /discharge/info"
            )
        pk = json_resp.get("PublicKey")
        if pk is None:
            raise bakery.ThirdPartyInfoNotFound(
                "no public key found in /discharge/info"
            )
        idm_pk = bakery.PublicKey.deserialize(pk)
        version = json_resp.get("Version", bakery.VERSION_1)
        self._cache[loc] = bakery.ThirdPartyInfo(
            version=version, public_key=idm_pk
        )
        return self._cache.get(loc)

    async def close(self):
        await self._session.close()
