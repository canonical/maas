#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the macaroon rewritten bits. They were taken from
- macaroonbakery/tests/test_agent.py
- macaroonbakery/tests/test_client.py
- macaroonbakery/tests/test_discharge_all.py
and they were adapted to match the new async logic.
"""

import base64
import datetime
from http.cookies import SimpleCookie
import json
import os
import tempfile
from urllib.parse import parse_qs, urlparse

from aiohttp import ClientRequest, web
from aiohttp.test_utils import unused_port
from aiohttp.web_middlewares import middleware
import macaroonbakery._utils as utils
import macaroonbakery.bakery as bakery
import macaroonbakery.checkers as checkers
import macaroonbakery.httpbakery as httpbakery
from macaroonbakery.httpbakery._error import (
    BAKERY_PROTOCOL_HEADER,
    DischargeError,
    ERR_DISCHARGE_REQUIRED,
)
import macaroonbakery.httpbakery.agent as agent
from macaroonbakery.httpbakery.agent import Agent, AuthInfo
from macaroonbakery.tests import common
import pymacaroons
from pymacaroons.verifier import Verifier
import pytest
from yarl import URL

from maasapiserver.common.auth.bakery import (
    AsyncAgentInteractor,
    discharge_all,
    HttpBakeryAsyncClient,
)
from maasapiserver.common.auth.models.exceptions import BakeryException

ONE_DAY = datetime.datetime.utcnow() + datetime.timedelta(days=1)
TEST_OP = bakery.Op(entity="test", action="test")

PUBLIC_KEY = "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE="
PRIVATE_KEY = "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU="

TEST_USER = "test-user"


@pytest.fixture
def new_bakery():
    def _new_bakery(location, locator=None, checker=None) -> bakery.Bakery:
        def check_is_something(ctx, cond, arg):
            if arg != "something":
                return f"{arg} doesn't match 'something'"
            return None

        if checker is None:
            c = checkers.Checker()
            c.namespace().register("testns", "")
            c.register("is", "testns", check_is_something)
            checker = c
        key = bakery.generate_key()
        return bakery.Bakery(
            location=location,
            locator=locator,
            key=key,
            checker=checker,
        )

    return _new_bakery


@pytest.fixture
def third_party_url():
    port = unused_port()
    return f"http://127.0.0.1:{port}"


class _DischargerLocator(bakery.ThirdPartyLocator):
    def __init__(self, loc: str, version=bakery.LATEST_VERSION):
        self.key = bakery.generate_key()
        self.loc = loc
        self.version = version

    def third_party_info(self, loc):
        if loc == self.loc:
            return bakery.ThirdPartyInfo(
                public_key=self.key.public_key,
                version=self.version,
            )


class FakeLocalServer:
    """
    Fake server to check authentication with macaroons.
    """

    def __init__(self, bakery_instance, auth_location=None, expiry=ONE_DAY):
        self._bakery = bakery_instance
        self._auth_location = auth_location
        self._caveats = None
        self._expiry = expiry
        self.headers = {BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION)}

    async def _write_discharge_error(
        self, exc: bakery.PermissionDenied | bakery.VerificationError
    ):
        caveats = []
        if self._auth_location is not None:
            caveats = [
                checkers.Caveat(
                    location=self._auth_location, condition="is-ok"
                )
            ]
        if self._caveats is not None:
            caveats.extend(self._caveats)
        macaroon = self._bakery.oven.macaroon(
            version=bakery.LATEST_VERSION,
            expiry=self._expiry,
            caveats=caveats,
            ops=[TEST_OP],
        )
        content, headers = httpbakery.discharge_required_response(
            macaroon=macaroon,
            path="/",
            cookie_suffix_name="test",
            message=exc.args[0],
        )
        headers.update(self.headers)
        return web.Response(body=content, status=401, headers=headers)

    @middleware
    async def middleware(self, request, handler):
        ctx = checkers.AuthContext()
        auth_checker = self._bakery.checker.auth(
            httpbakery.extract_macaroons(request.headers)
        )
        try:
            auth_checker.allow(ctx, [TEST_OP])
        except (bakery.PermissionDenied, bakery.VerificationError) as exc:
            return await self._write_discharge_error(exc)
        response = await handler(request)
        return response

    async def dummy_handler(self, request):
        return web.Response(text="done", headers=self.headers)

    async def run_web_server(self):
        app = web.Application(middlewares=[self.middleware])
        app.add_routes([web.route("*", "/", self.dummy_handler)])
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", unused_port())
        await site.start()
        return site


class FakeThirdPartyServer:
    """
    Fake third party server to handle discharge requests.
    """

    def __init__(self, locator: _DischargerLocator, url: str) -> None:
        self.locator = locator
        self.url = url
        self.headers = {BAKERY_PROTOCOL_HEADER: str(bakery.LATEST_VERSION)}
        self.info = None

    async def login_handler(self, request):
        qs = parse_qs(urlparse(request.url).query)
        assert request.method == "GET"
        assert qs == {"username": [TEST_USER], "public-key": [PUBLIC_KEY]}
        b = bakery.Bakery(key=bakery.generate_key())
        m = b.oven.macaroon(
            version=bakery.LATEST_VERSION,
            expiry=ONE_DAY,
            caveats=[
                bakery.local_third_party_caveat(
                    PUBLIC_KEY,
                    version=httpbakery.request_version(request.headers),
                )
            ],
            ops=[bakery.Op(entity="agent", action="login")],
        )
        resp = {"macaroon": m.to_dict()}
        return web.json_response(resp, headers=self.headers)

    async def discharge_handler(self, request):
        body = await request.text()
        qs = parse_qs(body)
        content = {q: qs[q][0] for q in qs}
        macaroon = httpbakery.discharge(
            checkers.AuthContext(),
            content,
            self.locator.key,
            self.locator,
            alwaysOK3rd,
        )
        resp = {"Macaroon": macaroon.to_dict()}
        return web.json_response(resp, headers=self.headers)

    async def visit_handler(self, request):
        if request.headers.get("Accept") in ("application/json", "*/*"):
            return web.json_response({"agent": "/agent-visit"})
        raise Exception("unexpected call to visit without Accept header")

    async def agent_visit_handler(self, request):
        if request.method != "POST":
            raise Exception("unexpected method")
        body = await request.json()
        if body["username"] != TEST_USER:
            raise Exception(
                "unexpected username in body {!r}".format(request.body)
            )
        public_key = bakery.PublicKey.deserialize(body["public_key"])
        ms = httpbakery.extract_macaroons(request.headers)
        if len(ms) == 0:
            b = bakery.Bakery(key=self.locator.key)
            m = b.oven.macaroon(
                version=bakery.LATEST_VERSION,
                expiry=ONE_DAY,
                caveats=[
                    bakery.local_third_party_caveat(
                        public_key,
                        version=httpbakery.request_version(request.headers),
                    )
                ],
                ops=[bakery.Op(entity="agent", action="login")],
            )
            content, headers = httpbakery.discharge_required_response(
                m, "/", "test", "message"
            )
            return web.Response(body=content, status=401, headers=headers)

        return web.json_response({"agent_login": True})

    async def wait_handler(self, request):
        class EmptyChecker(bakery.ThirdPartyCaveatChecker):
            def check_third_party_caveat(self, ctx, info):
                return []

        if self.info is None:
            raise Exception("visit url has not been visited")
        m = bakery.discharge(
            checkers.AuthContext(),
            self.info.id,
            self.info.caveat,
            self.locator.key,
            EmptyChecker(),
            _DischargerLocator(self.url),
        )
        return web.json_response({"Macaroon": m.to_dict()})

    async def run_web_server(self):
        app = web.Application()
        app.add_routes(
            [
                web.post("/discharge", self.discharge_handler),
                web.get("/login", self.login_handler),
                web.route("*", "/visit", self.visit_handler),
                web.route("*", "/agent-visit", self.agent_visit_handler),
                web.route("*", "/wait", self.wait_handler),
            ]
        )
        runner = web.AppRunner(app)
        await runner.setup()
        host, port = self.url.lstrip("http://").split(":")
        site = web.TCPSite(runner, host, int(port))
        await site.start()
        return site


class ThirdPartyCaveatCheckerF(bakery.ThirdPartyCaveatChecker):
    def __init__(self, check):
        self._check = check

    def check_third_party_caveat(self, ctx, info):
        cond, arg = checkers.parse_caveat(info.condition)
        return self._check(cond, arg)


alwaysOK3rd = ThirdPartyCaveatCheckerF(lambda cond, arg: [])


@pytest.mark.asyncio
class TestHttpBakeryAsyncClient:
    async def test_single_service_first_party(self, new_bakery):
        client = HttpBakeryAsyncClient()
        b = new_bakery("loc")
        server = await FakeLocalServer(b).run_web_server()

        srv_macaroon = b.oven.macaroon(
            version=bakery.LATEST_VERSION,
            expiry=ONE_DAY,
            caveats=None,
            ops=[TEST_OP],
        )

        assert srv_macaroon.macaroon.location == "loc"

        c = SimpleCookie()
        c["macaroon-test"] = base64.b64encode(
            json.dumps([srv_macaroon.to_dict().get("m")]).encode("utf-8")
        ).decode("utf-8")
        client._session.cookie_jar.update_cookies(c)

        url = server.name
        expected_response = "done"

        resp = await client.request(method="GET", url=url)
        assert (await resp.text()) == expected_response

        await client.close()
        await server.stop()

    async def test_single_service_third_party(
        self, new_bakery, third_party_url
    ):
        client = HttpBakeryAsyncClient()
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)
        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()

        url = local_server.name
        expected_response = "done"
        resp = await client.request(method="GET", url=url)
        assert (await resp.text()) == expected_response

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_single_service_third_party_with_path(
        self, new_bakery, third_party_url
    ):
        url = f"{third_party_url}/some/path"
        client = HttpBakeryAsyncClient()
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()

        expected_response = "done"

        url = local_server.name
        resp = await client.request(method="GET", url=url)
        assert (await resp.text()) == expected_response

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_single_service_third_party_version_1_caveat(
        self, new_bakery, third_party_url
    ):
        client = HttpBakeryAsyncClient()
        d = _DischargerLocator(third_party_url, version=bakery.VERSION_1)
        b = new_bakery("loc", d)

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()

        expected_response = "done"

        url = local_server.name
        resp = await client.request(method="GET", url=url)
        assert (await resp.text()) == expected_response

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_cookie_domain_host_not_fqdn(self, new_bakery):
        # See
        # https://github.com/go-macaroon-bakery/py-macaroon-bakery/issues/53

        b = new_bakery("loc")
        client = HttpBakeryAsyncClient()
        local_server = await FakeLocalServer(b).run_web_server()

        srv_macaroon = b.oven.macaroon(
            version=bakery.LATEST_VERSION,
            expiry=ONE_DAY,
            caveats=None,
            ops=[TEST_OP],
        )

        assert srv_macaroon.macaroon.location == "loc"

        # A discharge required response is expected here
        expected_response = ERR_DISCHARGE_REQUIRED

        # Note: by using "localhost" we're triggering the no-FQDN logic in the cookie code.
        url = f"http://localhost:{local_server._port}"

        with pytest.raises(BakeryException):
            resp = await client.request(method="GET", url=url)
            resp_json = await resp.json()
            assert resp_json.get("Code") == expected_response

            cookie_jar = client._session.cookie_jar
            for cookie in cookie_jar:
                # there should be only this cookie
                assert cookie.key == "macaroon-test"
                assert cookie["domain"] == "localhost.local"

        await client.close()
        await local_server.stop()

    async def test_single_party_with_header(self, new_bakery):
        b = new_bakery("loc")
        client = HttpBakeryAsyncClient()
        local_server = await FakeLocalServer(b).run_web_server()

        srv_macaroon = b.oven.macaroon(
            version=bakery.LATEST_VERSION,
            expiry=ONE_DAY,
            caveats=None,
            ops=[TEST_OP],
        )

        assert srv_macaroon.macaroon.location == "loc"

        expected_response = "done"
        headers = {
            "Macaroons": str(
                base64.b64encode(
                    json.dumps([srv_macaroon.to_dict().get("m")]).encode(
                        "utf-8"
                    )
                )
            )
        }

        url = local_server.name

        resp = await client.request(method="GET", url=url, headers=headers)
        assert (await resp.text()) == expected_response

        await client.close()
        await local_server.stop()

    async def test_expiry_cookie_is_set(self, new_bakery, third_party_url):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        client = HttpBakeryAsyncClient()

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()

        expected_response = "done"

        url = local_server.name
        resp = await client.request(method="GET", url=url)
        assert (await resp.text()) == expected_response

        cookie = None
        for c in client._session.cookie_jar:
            if c.key == "macaroon-test":
                cookie = c
                break

        assert cookie is not None
        m = bakery.Macaroon.from_dict(
            json.loads(base64.b64decode(cookie.value).decode("utf-8"))[0]
        )
        t = checkers.macaroons_expiry_time(checkers.Namespace(), [m.macaroon])
        assert t == ONE_DAY

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_expiry_cookie_set_in_past(
        self, new_bakery, third_party_url
    ):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        client = HttpBakeryAsyncClient()

        YESTERDAY = datetime.datetime.utcnow() - datetime.timedelta(days=1)

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url, expiry=YESTERDAY
        ).run_web_server()

        url = local_server.name
        with pytest.raises(BakeryException) as exc_info:
            await client.request(method="GET", url=url)

        assert exc_info.value.args[0] == "too many (3) discharge requests"

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_too_many_discharge(
        self, new_bakery, third_party_url, monkeypatch
    ):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()

        wrong_macaroon = bakery.Macaroon(
            root_key=b"some key",
            id=b"xxx",
            location="some other location",
            version=bakery.VERSION_0,
        )

        discharge_response = {"Macaroon": wrong_macaroon.to_dict()}

        async def monkey_patch_discharge_handler(self, request):
            return web.json_response(
                discharge_response, status=200, headers=self.headers
            )

        # monkey patch the discharge_handler to supply a wrong macaroon
        monkeypatch.setattr(
            FakeThirdPartyServer,
            "discharge_handler",
            monkey_patch_discharge_handler,
        )

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()

        client = HttpBakeryAsyncClient()

        url = local_server.name

        with pytest.raises(BakeryException) as exc_info:
            await client.request(method="GET", url=url)

        assert exc_info.value.args[0] == "too many (3) discharge requests"

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_third_party_discharge_refused(
        self, new_bakery, third_party_url, monkeypatch
    ):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        def check(cond, arg):
            raise bakery.ThirdPartyCaveatCheckFailed("boo! cond " + cond)

        async def monkey_patch_discharge_handler(self, request):
            body = await request.text()
            qs = parse_qs(body)
            content = {q: qs[q][0] for q in qs}
            with pytest.raises(bakery.ThirdPartyCaveatCheckFailed) as exc_info:
                httpbakery.discharge(
                    checkers.AuthContext(),
                    content,
                    self.locator.key,
                    self.locator,
                    ThirdPartyCaveatCheckerF(check),
                )
            # assert here the actual exception we want to test against
            assert exc_info.value == "boo! cond is-ok"
            return web.json_response({}, status=503, headers=self.headers)

        monkeypatch.setattr(
            FakeThirdPartyServer,
            "discharge_handler",
            monkey_patch_discharge_handler,
        )

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()
        client = HttpBakeryAsyncClient()
        url = local_server.name

        # here we are testing that the bakery.ThirdPartyCaveatCheckFailed exception is properly raised,
        # however, we should return a response to the client, and that response is a DischargeError
        with pytest.raises(DischargeError):
            await client.request(method="GET", url=url)

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_discharge_jsondecodeerror(
        self, new_bakery, third_party_url, monkeypatch
    ):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        async def monkey_patch_discharge_handler(self, request):
            resp = b"bad system"
            headers = {"Content-Type": "application/json"}
            headers.update(self.headers)
            return web.Response(body=resp, status=503)

        monkeypatch.setattr(
            FakeThirdPartyServer,
            "discharge_handler",
            monkey_patch_discharge_handler,
        )

        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()
        local_server = await FakeLocalServer(
            b, auth_location=third_party_url
        ).run_web_server()

        client = HttpBakeryAsyncClient()
        url = local_server.name

        with pytest.raises(DischargeError) as exc_info:
            await client.request(method="GET", url=url)

        assert (
            exc_info.value.args[0]
            == "third party refused dischargex: unexpected response: [503] b'bad system'"
        )

        await client.close()
        await third_party_server.stop()
        await local_server.stop()

    async def test_extract_macaroons_from_request(self):
        def encode_macaroon(m):
            macaroons = "[" + utils.macaroon_to_json_string(m) + "]"
            return base64.urlsafe_b64encode(utils.to_bytes(macaroons)).decode(
                "ascii"
            )

        req = ClientRequest(method="GET", url=URL("http://example.com"))
        m1 = pymacaroons.Macaroon(
            version=pymacaroons.MACAROON_V2, identifier="one"
        )
        headers = {"Macaroons": encode_macaroon(m1)}
        req.update_headers(headers)
        m2 = pymacaroons.Macaroon(
            version=pymacaroons.MACAROON_V2, identifier="two"
        )
        c1 = SimpleCookie()
        c1["macaroon-auth"] = encode_macaroon(m2)
        c1["macaroon-auth"]["domain"] = "http://example.com"
        c2 = SimpleCookie()
        c2["macaroon-empty"] = ""
        c2["macaroon-empty"]["domain"] = "http://example.com"
        req.update_cookies(c1)
        req.update_cookies(c2)

        macaroons = httpbakery.extract_macaroons(req.headers)
        assert len(macaroons) == 2
        macaroons.sort(key=lambda ms: ms[0].identifier)
        assert macaroons[0][0].identifier == m1.identifier
        assert macaroons[1][0].identifier == m2.identifier

    async def test_handle_error_cookie_path(self):
        macaroon = bakery.Macaroon(
            root_key=b"some key",
            id=b"xxx",
            location="some location",
            version=bakery.VERSION_0,
        )
        info = {
            "Macaroon": macaroon.to_dict(),
            "MacaroonPath": ".",
            "CookieNameSuffix": "test",
        }
        error = httpbakery.Error(
            code=407,
            message="error",
            version=bakery.LATEST_VERSION,
            info=httpbakery.ErrorInfo.from_dict(info),
        )
        client = HttpBakeryAsyncClient()
        await client.handle_error(error, URL("http://example.com/some/path"))

        for cookie in client._session.cookie_jar:
            assert cookie["path"] == "/some/"

        await client.close()


@pytest.fixture
def auth_info(third_party_url) -> AuthInfo:
    key = bakery.PrivateKey.deserialize(PRIVATE_KEY)
    agent = Agent(url=third_party_url, username=TEST_USER)
    return AuthInfo(key=key, agents=[agent])


def load_file(file):
    fd, filename = tempfile.mkstemp()
    with os.fdopen(fd, "w") as f:
        f.write(file)
    return filename


class TestAsyncAgentInteractor:
    def test_load_auth_info(self):
        filename = load_file(agent_file)
        auth_info = agent.load_auth_info(filename)
        assert str(auth_info.key) == PRIVATE_KEY
        assert str(auth_info.key.public_key) == PUBLIC_KEY
        assert auth_info.agents == [
            agent.Agent(url="https://1.example.com/", username="user-1"),
            agent.Agent(
                url="https://2.example.com/discharger", username="user-2"
            ),
            agent.Agent(url="http://0.3.2.1", username=TEST_USER),
        ]
        os.remove(filename)

    def test_invalid_agent_json(self):
        with pytest.raises(agent.AgentFileFormatError):
            agent.read_auth_info("}")

    def test_invalid_read_auth_info_arg(self):
        with pytest.raises(agent.AgentFileFormatError):
            agent.read_auth_info(0)

    def test_load_auth_info_with_bad_key(self):
        filename = load_file(bad_key_agent_file)
        with pytest.raises(agent.AgentFileFormatError):
            agent.load_auth_info(filename)
        os.remove(filename)

    def test_load_auth_info_with_no_username(self):
        filename = load_file(no_username_agent_file)
        with pytest.raises(agent.AgentFileFormatError):
            agent.load_auth_info(filename)
        os.remove(filename)

    async def test_agent_login(self, new_bakery, third_party_url, auth_info):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)
        local_server = await FakeLocalServer(
            b, third_party_url
        ).run_web_server()
        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()

        async_agent = AsyncAgentInteractor(auth_info=auth_info)
        client = HttpBakeryAsyncClient(interaction_methods=[async_agent])

        url = local_server.name
        resp = await client.request(method="GET", url=url)
        assert (await resp.text()) == "done"

        await client.close()
        await local_server.stop()
        await third_party_server.stop()

    async def test_agent_legacy(
        self, new_bakery, third_party_url, auth_info, monkeypatch
    ):
        d = _DischargerLocator(third_party_url)
        b = new_bakery("loc", d)

        async def monkey_patch_discharge_handler(self, request):
            body = await request.text()
            qs = parse_qs(body)

            if qs.get("caveat64") is not None:
                content = {q: qs[q][0] for q in qs}

                class InteractionRequiredError(Exception):
                    def __init__(self, info, error):
                        self.info = info
                        self.error = error

                class CheckerInError(bakery.ThirdPartyCaveatChecker):
                    def __init__(self, url):
                        self._url = url

                    def check_third_party_caveat(self, ctx, info):
                        raise InteractionRequiredError(
                            info,
                            httpbakery.Error(
                                code=httpbakery.ERR_INTERACTION_REQUIRED,
                                version=httpbakery.request_version(
                                    request.headers
                                ),
                                message="interaction required",
                                info=httpbakery.ErrorInfo(
                                    wait_url=f"{self._url}/wait?dischargeid=1",
                                    visit_url=f"{self._url}/visit?dischargeid=1",
                                ),
                            ),
                        )

                try:
                    macaroon = httpbakery.discharge(
                        checkers.AuthContext(),
                        content,
                        self.locator.key,
                        None,
                        CheckerInError(self.url),
                    )
                    resp = {"Macaroon": macaroon.to_dict()}
                    return web.json_response(resp, headers=self.headers)
                except InteractionRequiredError as exc:
                    self.info = exc.info
                    resp = {
                        "Code": exc.error.code,
                        "Message": exc.error.message,
                        "Info": {
                            "WaitURL": exc.error.info.wait_url,
                            "VisitURL": exc.error.info.visit_url,
                        },
                    }
                    return web.json_response(
                        resp, status=401, headers=self.headers
                    )

        monkeypatch.setattr(
            FakeThirdPartyServer,
            "discharge_handler",
            monkey_patch_discharge_handler,
        )

        local_server = await FakeLocalServer(
            b, third_party_url
        ).run_web_server()
        third_party_server = await FakeThirdPartyServer(
            d, third_party_url
        ).run_web_server()

        async_agent = AsyncAgentInteractor(auth_info=auth_info)
        client = HttpBakeryAsyncClient(interaction_methods=[async_agent])

        url = local_server.name
        resp = await client.request(method="GET", url=url)

        assert (await resp.text()) == "done"

        await client.close()
        await local_server.stop()
        await third_party_server.stop()


async def always_ok(predicate):
    return True


class TestDischargeAll:
    async def test_discharge_all_no_discharges(self):
        root_key = b"root key"
        m = bakery.Macaroon(
            root_key=root_key,
            id=b"id0",
            location="loc0",
            version=bakery.LATEST_VERSION,
            namespace=common.test_checker().namespace(),
        )
        ms = await discharge_all(m, no_discharge())
        assert len(ms) == 1
        assert ms[0] == m.macaroon
        v = Verifier()
        v.satisfy_general(always_ok)
        v.verify(m.macaroon, root_key, None)

    async def test_discharge_all_many_discharges(self):
        root_key = b"root key"
        m0 = bakery.Macaroon(
            root_key=root_key,
            id=b"id0",
            location="loc0",
            version=bakery.LATEST_VERSION,
        )

        class State(object):
            total_required = 40
            id = 1

        def add_caveats(m):
            for i in range(0, 1):
                if State.total_required == 0:
                    break
                cid = "id{}".format(State.id)
                m.macaroon.add_third_party_caveat(
                    location="somewhere",
                    key="root key {}".format(cid).encode("utf-8"),
                    key_id=cid.encode("utf-8"),
                )
                State.id += 1
                State.total_required -= 1

        add_caveats(m0)

        async def get_discharge(cav, payload):
            assert payload is None
            m = bakery.Macaroon(
                root_key="root key {}".format(
                    cav.caveat_id.decode("utf-8")
                ).encode("utf-8"),
                id=cav.caveat_id,
                location="",
                version=bakery.LATEST_VERSION,
            )

            add_caveats(m)
            return m

        ms = await discharge_all(m0, get_discharge)

        assert len(ms) == 41

        v = Verifier()
        v.satisfy_general(always_ok)
        v.verify(ms[0], root_key, ms[1:])

    async def test_discharge_all_many_discharges_with_real_third_party_caveats(
        self,
    ):
        # This is the same flow as TestDischargeAllManyDischarges except that
        # we're using actual third party caveats as added by
        # Macaroon.add_caveat and we use a larger number of caveats
        # so that caveat ids will need to get larger.
        locator = bakery.ThirdPartyStore()
        bakeries = {}
        total_discharges_required = 40

        class M:
            bakery_id = 0
            still_required = total_discharges_required

        def add_bakery():
            M.bakery_id += 1
            loc = "loc{}".format(M.bakery_id)
            bakeries[loc] = common.new_bakery(loc, locator)
            return loc

        ts = common.new_bakery("ts-loc", locator)

        def checker(_, ci):
            caveats = []
            if ci.condition != "something":
                self.fail("unexpected condition")
            for i in range(0, 2):
                if M.still_required <= 0:
                    break
                caveats.append(
                    checkers.Caveat(
                        location=add_bakery(), condition="something"
                    )
                )
                M.still_required -= 1
            return caveats

        root_key = b"root key"
        m0 = bakery.Macaroon(
            root_key=root_key,
            id=b"id0",
            location="ts-loc",
            version=bakery.LATEST_VERSION,
        )

        m0.add_caveat(
            checkers.Caveat(location=add_bakery(), condition="something"),
            ts.oven.key,
            locator,
        )

        # We've added a caveat (the first) so one less caveat is required.
        M.still_required -= 1

        class ThirdPartyCaveatCheckerF(bakery.ThirdPartyCaveatChecker):
            def check_third_party_caveat(self, ctx, info):
                return checker(ctx, info)

        async def get_discharge(cav, payload):
            return bakery.discharge(
                common.test_context,
                cav.caveat_id,
                payload,
                bakeries[cav.location].oven.key,
                ThirdPartyCaveatCheckerF(),
                locator,
            )

        ms = await discharge_all(m0, get_discharge)

        assert len(ms) == total_discharges_required + 1

        v = Verifier()
        v.satisfy_general(always_ok)
        v.verify(ms[0], root_key, ms[1:])

    async def test_discharge_all_local_discharge(self):
        oc = common.new_bakery("ts", None)
        client_key = bakery.generate_key()
        m = oc.oven.macaroon(
            bakery.LATEST_VERSION,
            common.ages,
            [
                bakery.local_third_party_caveat(
                    client_key.public_key, bakery.LATEST_VERSION
                )
            ],
            [bakery.LOGIN_OP],
        )
        ms = await discharge_all(m, no_discharge(), client_key)
        oc.checker.auth([ms]).allow(common.test_context, [bakery.LOGIN_OP])

    async def test_discharge_all_local_discharge_version1(self):
        oc = common.new_bakery("ts", None)
        client_key = bakery.generate_key()
        m = oc.oven.macaroon(
            bakery.VERSION_1,
            common.ages,
            [
                bakery.local_third_party_caveat(
                    client_key.public_key, bakery.VERSION_1
                )
            ],
            [bakery.LOGIN_OP],
        )
        ms = await discharge_all(m, no_discharge(), client_key)
        oc.checker.auth([ms]).allow(common.test_context, [bakery.LOGIN_OP])


def no_discharge():
    async def get_discharge(cav, payload):
        pytest.fail("get_discharge called unexpectedly")

    return get_discharge


agent_file = """
{
  "key": {
    "public": "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=",
    "private": "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU="
    },
  "agents": [{
    "url": "https://1.example.com/",
    "username": "user-1"
    }, {
    "url": "https://2.example.com/discharger",
    "username": "user-2"
  }, {
    "url": "http://0.3.2.1",
    "username": "test-user"
  }]
}
"""

bad_key_agent_file = """
{
  "key": {
    "public": "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=",
    "private": "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJE=="
    },
  "agents": [{
    "url": "https://1.example.com/",
    "username": "user-1"
    }, {
    "url": "https://2.example.com/discharger",
    "username": "user-2"
  }]
}
"""


no_username_agent_file = """
{
  "key": {
    "public": "YAhRSsth3a36mRYqQGQaLiS4QJax0p356nd+B8x7UQE=",
    "private": "CqoSgj06Zcgb4/S6RT4DpTjLAfKoznEY3JsShSjKJEU="
    },
  "agents": [{
    "url": "https://1.example.com/"
    }, {
    "url": "https://2.example.com/discharger",
    "username": "user-2"
  }]
}
"""
