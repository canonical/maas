#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""
Async rewrite of the macaroonbakery lib parts that we use.
This is necessary to avoid synchronous requests calls.
"""

import base64
from collections import namedtuple
import copy
from http.cookies import SimpleCookie
import ipaddress
import ssl
from typing import Awaitable, Callable
from urllib.parse import urljoin, urlparse

from aiohttp import (
    ClientResponse,
    ClientSession,
    ContentTypeError,
    CookieJar,
    TCPConnector,
)
from macaroonbakery import _utils as utils
from macaroonbakery import bakery, checkers, httpbakery
from macaroonbakery.bakery._discharge import (
    _EmptyLocator,
    _LocalDischargeChecker,
    discharge,
    emptyContext,
)
from macaroonbakery.bakery._error import ThirdPartyCaveatCheckFailed
from macaroonbakery.httpbakery._client import (
    _add_json_binary_field,
    MAX_DISCHARGE_RETRIES,
)
from macaroonbakery.httpbakery._error import (
    BAKERY_PROTOCOL_HEADER,
    DischargeError,
    ERR_DISCHARGE_REQUIRED,
    ERR_INTERACTION_REQUIRED,
    Error,
    InteractionError,
    InteractionMethodNotFound,
)
from macaroonbakery.httpbakery.agent import AgentInteractor
from macaroonbakery.httpbakery.agent._agent import InteractionInfo
from yarl import URL

from maasapiserver.common.auth.models.exceptions import BakeryException


def _is_ip_address(host) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


async def discharge_all(
    m: bakery.Macaroon,
    get_discharge: Callable[..., Awaitable[bakery.Macaroon]],
    local_key=None,
):
    """Async rewrite of macaroonbakery.bakery._discharge.discharge_all"""
    primary = m.macaroon
    discharges = [primary]

    # cav holds the macaroon caveat that needs discharge.
    # encrypted_caveat (bytes) holds encrypted caveat if it was held
    # externally.
    _NeedCaveat = namedtuple("_NeedCaveat", "cav encrypted_caveat")
    need = []

    def add_caveats(m):
        for cav in m.macaroon.caveats:
            if cav.location is None or cav.location == "":
                continue
            encrypted_caveat = m.caveat_data.get(cav.caveat_id, None)
            need.append(
                _NeedCaveat(cav=cav, encrypted_caveat=encrypted_caveat)
            )

    add_caveats(m)
    while len(need) > 0:
        cav = need[0]
        need = need[1:]
        if cav.cav.location == "local":
            if local_key is None:
                raise ThirdPartyCaveatCheckFailed(
                    "found local third party caveat but no private key provided",
                )
            # TODO use a small caveat id.
            dm = discharge(
                ctx=emptyContext,
                key=local_key,
                checker=_LocalDischargeChecker(),
                caveat=cav.encrypted_caveat,
                id=cav.cav.caveat_id_bytes,
                locator=_EmptyLocator(),
            )
        else:
            dm = await get_discharge(cav.cav, cav.encrypted_caveat)
        # It doesn't matter that we're invalidating dm here because we're
        # about to throw it away.
        discharge_m = dm.macaroon
        m = primary.prepare_for_request(discharge_m)
        discharges.append(m)
        add_caveats(dm)
    return discharges


class HttpBakeryAsyncClient:
    """
    Async rewrite of macaroonbakery.httpbakery.Client.
    It doesn't support WebBrowser-based agents.
    """

    BAKERY_HEADERS = {BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION)}

    def __init__(self, interaction_methods=None, key=None):
        # we need unsafe=True to save cookies from IPs
        context = ssl.create_default_context()
        tcp_conn = TCPConnector(ssl=context)
        self._session = ClientSession(
            headers=self.BAKERY_HEADERS,
            trust_env=True,
            cookie_jar=CookieJar(unsafe=True),
            connector=tcp_conn,
        )
        if interaction_methods is None:
            interaction_methods = []

        self._interaction_methods = interaction_methods
        self.key = key

    async def close(self) -> None:
        await self._session.close()

    async def request(self, method, url, **kwargs) -> ClientResponse:
        response = await self._session.request(
            method=method, url=url, **kwargs
        )
        retries = 0
        while True:
            if response.status not in (401, 407):
                return response
            if (
                response.status == 401
                and response.headers.get("WWW-Authenticate") != "Macaroon"
            ):
                return response

            if response.headers.get("Content-Type") != "application/json":
                return response
            errorJSON = await response.json()
            if errorJSON.get("Code") != ERR_DISCHARGE_REQUIRED:
                return response
            retries += 1
            if retries >= MAX_DISCHARGE_RETRIES:
                raise BakeryException(
                    f"too many ({retries}) discharge requests"
                )
            error = Error.from_dict(errorJSON)
            await self.handle_error(error, response.url)
            response = await self._session.request(
                response.method, response.url, **kwargs
            )

    async def handle_error(self, error: Error, url: URL) -> None:
        if error.info is None or error.info.macaroon is None:
            raise BakeryException(
                "unable to read info in discharge error response"
            )

        discharges = await discharge_all(
            error.info.macaroon,
            self.acquire_discharge,
            self.key,
        )
        macaroons = (
            "["
            + ",".join(map(utils.macaroon_to_json_string, discharges))
            + "]"
        )
        all_macaroons = base64.urlsafe_b64encode(utils.to_bytes(macaroons))

        full_path = urljoin(str(url), error.info.macaroon_path)
        if error.info.cookie_name_suffix is not None:
            name = "macaroon-" + error.info.cookie_name_suffix
        else:
            name = "macaroon-auth"
        expires = checkers.macaroons_expiry_time(
            checkers.Namespace(), discharges
        )
        parsed_url = urlparse(full_path)
        domain = str(parsed_url.hostname)

        if "." not in domain and not _is_ip_address(domain):
            domain += ".local"
        cookie = SimpleCookie()
        cookie[name] = all_macaroons.decode("ascii")
        cookie[name]["domain"] = domain
        cookie[name]["path"] = parsed_url.path
        if expires is not None and expires.tzinfo is None:
            cookie[name]["expires"] = expires.strftime(
                "%a, %d %b %Y %H:%M:%S GMT"
            )
        self._session.cookie_jar.update_cookies(cookie)

    async def acquire_discharge(self, cav, payload) -> bakery.Macaroon:
        """Request a discharge macaroon from the caveat location
        as an HTTP URL.
        @param cav Third party {pymacaroons.Caveat} to be discharged.
        @param payload External caveat data {bytes}.
        @return The acquired macaroon {macaroonbakery.Macaroon}
        """
        resp = await self._acquire_discharge_with_token(cav, payload, None)
        try:
            resp_json = await resp.json()
        except ContentTypeError:
            resp_json = None
        # TODO Fabrice what is the other http response possible ??
        if resp.status == 200 and resp_json is not None:
            return bakery.Macaroon.from_dict(resp_json.get("Macaroon"))
        # A 5xx error might not return json.
        try:
            cause = Error.from_dict(resp_json)
        except (ValueError, AttributeError):
            raise DischargeError(
                f"unexpected response: [{resp.status}] {(await resp.read())}"
            )
        if cause.code != ERR_INTERACTION_REQUIRED:
            raise DischargeError(cause.message)
        if cause.info is None:
            raise DischargeError(
                f"interaction-required response with no info: {resp_json}"
            )
        loc = cav.location
        if not loc.endswith("/"):
            loc = loc + "/"
        token, m = await self._interact(loc, cause, payload)
        if m is not None:
            # We've acquired the macaroon directly via legacy interaction.
            return m
        # Try to acquire the discharge again, but this time with
        # the token acquired by the interaction method.
        resp = await self._acquire_discharge_with_token(cav, payload, token)
        if resp.status == 200:
            return bakery.Macaroon.from_dict(
                (await resp.json()).get("Macaroon")
            )
        else:
            raise DischargeError(f"discharge failed with code {resp.status}")

    async def _acquire_discharge_with_token(
        self, cav, payload, token
    ) -> ClientResponse:
        req = {}
        _add_json_binary_field(cav.caveat_id_bytes, req, "id")
        if token is not None:
            _add_json_binary_field(token.value, req, "token")
            req["token-kind"] = token.kind
        if payload is not None:
            req["caveat64"] = (
                base64.urlsafe_b64encode(payload).rstrip(b"=").decode("utf-8")
            )
        loc = cav.location
        if not loc.endswith("/"):
            loc += "/"
        target = urljoin(loc, "discharge")
        return await self._session.request(method="POST", url=target, data=req)

    async def _interact(self, location, error_info, payload):
        """Gathers a macaroon by directing the user to interact with a
        web page. The error_info argument holds the interaction-required
        error response.
        @return DischargeToken, bakery.Macaroon
        """
        if (
            self._interaction_methods is None
            or len(self._interaction_methods) == 0
        ):
            raise InteractionError("interaction required but not possible")
        # TODO(rogpeppe) make the robust against a wider range of error info.
        if (
            error_info.info.interaction_methods is None
            and error_info.info.visit_url is not None
        ):
            # It's an old-style error; deal with it differently.
            return None, await self._legacy_interact(location, error_info)
        for interactor in self._interaction_methods:
            found = error_info.info.interaction_methods.get(interactor.kind())
            if found is None:
                continue
            try:
                token = await interactor.interact(self, location, error_info)
            except InteractionMethodNotFound:
                continue
            if token is None:
                raise InteractionError(
                    "interaction method returned an empty token"
                )
            return token, None

        raise InteractionError("no supported interaction method")

    async def _legacy_interact(self, location, error_info) -> bakery.Macaroon:
        visit_url = urljoin(location, error_info.info.visit_url)
        wait_url = urljoin(location, error_info.info.wait_url)
        method_urls = await self._legacy_get_interaction_methods(visit_url)
        for interactor in self._interaction_methods:
            kind = interactor.kind()

            visit_url = method_urls.get(kind)
            if visit_url is None:
                continue

            visit_url = urljoin(location, visit_url)
            await interactor.legacy_interact(self, location, visit_url)
            macaroon_resp = await self.request(method="GET", url=wait_url)
            if macaroon_resp.status != 200:
                raise InteractionError(f"cannot get {wait_url}")
            macaroon = (await macaroon_resp.json()).get("Macaroon")
            return bakery.Macaroon.from_dict(macaroon)

        raise InteractionError(
            "no methods supported; supported [{}]; provided [{}]".format(
                " ".join([x.kind() for x in self._interaction_methods]),
                " ".join(method_urls.keys()),
            )
        )

    async def _legacy_get_interaction_methods(self, u):
        """Queries a URL as found in an ErrInteractionRequired VisitURL field to
        find available interaction methods.
        It does this by sending a GET request to the URL with the Accept
        header set to "application/json" and parsing the resulting
        response as a dict.
        """
        resp = await self.request(method="GET", url=u)
        method_urls = {}
        if resp.status == 200:
            json_resp = await resp.json()
            for m in json_resp:
                method_urls[m] = urljoin(u, json_resp[m])

        if method_urls.get("interactive") is None:
            # There's no "interactive" method returned, but we know
            # the server does actually support it, because all dischargers
            # are required to, so fill it in with the original URL.
            method_urls["interactive"] = u
        return method_urls


class AsyncAgentInteractor(AgentInteractor):
    """Async rewrite of macaroonbakery.httpbakery.agent._agent.AgentInteractor."""

    async def interact(
        self, client: HttpBakeryAsyncClient, location, interaction_required_err
    ) -> httpbakery.DischargeToken:
        p = interaction_required_err.interaction_method(
            "agent", InteractionInfo
        )
        if p.login_url is None or p.login_url == "":
            raise httpbakery.InteractionError(
                "no login-url field found in agent interaction method"
            )
        agent = self._find_agent(location)
        if not location.endswith("/"):
            location += "/"
        login_url = urljoin(location, p.login_url)
        params = {
            "username": agent.username,
            "public-key": str(self._auth_info.key.public_key),
        }
        resp = await client._session.request(
            method="GET", url=login_url, params=params
        )
        if resp.status != 200:
            raise httpbakery.InteractionError(
                f"cannot acquire agent macaroon: {resp.status} {resp.content}"
            )
        m = (await resp.json()).get("macaroon")
        if m is None:
            raise httpbakery.InteractionError("no macaroon in response")
        m = bakery.Macaroon.from_dict(m)
        ms = await discharge_all(m, None, self._auth_info.key)
        b = bytearray()
        for m in ms:
            b.extend(utils.b64decode(m.serialize()))
        return httpbakery.DischargeToken(kind="agent", value=bytes(b))

    async def legacy_interact(
        self, client: HttpBakeryAsyncClient, location, visit_url
    ):
        """Implement LegacyInteractor.legacy_interact by obtaining
        the discharge macaroon using the client's private key
        """
        agent = self._find_agent(location)
        # Shallow-copy the client so that we don't unexpectedly side-effect
        # it by changing the key. Another possibility might be to
        # set up agent authentication differently, in such a way that
        # we're sure that client.key is the same as self._auth_info.key.
        client = copy.copy(client)
        client.key = self._auth_info.key
        resp = await client.request(
            method="POST",
            url=visit_url,
            json={
                "username": agent.username,
                "public_key": str(self._auth_info.key.public_key),
            },
        )
        if resp.status != 200:
            raise httpbakery.InteractionError(
                f"cannot acquire agent macaroon from {visit_url}: {resp.status} (response body: {resp.text})"
            )
        if not (await resp.json()).get("agent_login", False):
            raise httpbakery.InteractionError("agent login failed")
