# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from pathlib import Path
import ssl

import httpx
import pytest
from starlette.requests import Request

from maasapiserver.app import ServerConfig
from maasapiserver.main import craft_internal_app
from maasapiserver.tls import TLSPatchedH11Protocol


def _create_client_ssl_context(
    ca_cert: Path,
    client_cert: Path | None = None,
    client_key: Path | None = None,
) -> ssl.SSLContext:
    """Create an SSL context for the client with optional client certificate.

    This is the proper way to configure httpx with client certificates.
    The deprecated string-based API (verify=str, cert=(str, str)) doesn't
    send client certificates to servers configured with CERT_OPTIONAL.
    """
    ctx = ssl.create_default_context(cafile=str(ca_cert))
    if client_cert and client_key:
        ctx.load_cert_chain(str(client_cert), str(client_key))
    return ctx


def _get_test_file(filename: str) -> Path:
    return Path(__file__).parent / "data_test_main" / filename


@pytest.fixture
def ca_cert():
    yield _get_test_file("ca.pem")


@pytest.fixture
async def server(db, ca_cert):
    """Serve the internal app over mTLS and yield its base URL.

    The port is ephemeral so that concurrent workers (pytest-xdist) or
    repeated runs can't collide on a fixed one.
    """
    server_cert = _get_test_file("server.pem")
    server_key = _get_test_file("server.key")

    app = craft_internal_app(
        db,
        server_config=ServerConfig(
            host="localhost",
            port=0,
            ssl_certfile=str(server_cert),
            ssl_keyfile=str(server_key),
            ssl_ca_certs=str(ca_cert),
            ssl_cert_reqs=ssl.CERT_OPTIONAL,
            http=TLSPatchedH11Protocol,
        ),
    )

    async def index(request: Request):
        tls_info = request.scope.get("extensions", {}).get("tls", {})
        return {"tls": tls_info}

    app.fastapi_app.add_api_route("/test", endpoint=index, methods=["GET"])
    app.fastapi_app.add_api_route(
        "/rack_controllers:enroll", endpoint=index, methods=["POST"]
    )

    server = app.server

    # inspired from https://github.com/Kludex/uvicorn/blob/b8e65e49bfadf6d5ea30e56d0cd9f47329de606c/tests/utils.py#L9-L18
    cancel_handle = asyncio.ensure_future(server.serve())
    try:
        for _ in range(50):
            if server.started:
                break
            await asyncio.sleep(0.1)
        assert server.started, "internal app server did not start"
        # uvicorn has bound its sockets at this point; ask the OS which
        # ephemeral port it picked.
        port = server.servers[0].sockets[0].getsockname()[1]
        yield f"https://localhost:{port}"
    finally:
        await server.shutdown()
        cancel_handle.cancel()


@pytest.mark.asyncio
class TestMTLSInternalServer:
    async def test_mtls_with_signed_client_certs(self, server, ca_cert):
        client_cert = _get_test_file("client.pem")
        client_key = _get_test_file("client.key")

        ssl_context = _create_client_ssl_context(
            ca_cert, client_cert, client_key
        )
        async with httpx.AsyncClient(verify=ssl_context) as client:
            r1 = await client.get(f"{server}/test")
        assert r1.status_code == 200
        data1 = r1.json()
        tls_ext1 = data1["tls"]
        assert tls_ext1["tls_used"] is True
        assert tls_ext1["client_cn"] == "Good Agent"
        assert len(tls_ext1["client_cert_chain"]) == 1
        assert "tls_version" in tls_ext1

    async def test_mtls_rack_controller_enrol_endpoint(self, server, ca_cert):
        ssl_context = _create_client_ssl_context(ca_cert)
        async with httpx.AsyncClient(verify=ssl_context) as client:
            r2 = await client.post(f"{server}/rack_controllers:enroll")
        assert r2.status_code == 200
        data2 = r2.json()
        tls_ext2 = data2["tls"]
        assert tls_ext2["tls_used"] is True
        assert tls_ext2["client_cert_chain"] == []
        assert "tls_version" in tls_ext2

    async def test_mtls_client_certificate_is_required(self, server, ca_cert):
        ssl_context = _create_client_ssl_context(ca_cert)
        async with httpx.AsyncClient(verify=ssl_context) as client:
            r2 = await client.post(f"{server}/test")
        assert r2.status_code == 403

    async def test_mtls_with_wrong_ca(self, server):
        fake_ca_cert = _get_test_file("fake_ca.pem")
        client_cert = _get_test_file("client.pem")
        client_key = _get_test_file("client.key")

        ssl_context = _create_client_ssl_context(
            fake_ca_cert, client_cert, client_key
        )
        with pytest.raises(
            (httpx.ConnectError, ssl.SSLError, ssl.SSLCertVerificationError)
        ):
            async with httpx.AsyncClient(verify=ssl_context) as client:
                await client.get(f"{server}/test")

    async def test_mtls_with_wrong_key(self, server, ca_cert):
        client_cert = _get_test_file("client.pem")
        fake_client_key = _get_test_file("fake_client.key")

        with pytest.raises(ssl.SSLError):
            _create_client_ssl_context(ca_cert, client_cert, fake_client_key)

    async def test_mtls_with_wrong_cert(self, server, ca_cert):
        fake_client_cert = _get_test_file("fake_client.pem")
        client_key = _get_test_file("fake_client.key")

        ssl_context = _create_client_ssl_context(
            ca_cert, fake_client_cert, client_key
        )
        with pytest.raises(httpx.ReadError):
            async with httpx.AsyncClient(verify=ssl_context) as client:
                await client.get(f"{server}/test")

    async def test_mtls_with_fake_client_certificate(self, server, ca_cert):
        fake_client_cert = _get_test_file("fake_client.pem")
        fake_client_key = _get_test_file("fake_client.key")

        ssl_context = _create_client_ssl_context(
            ca_cert, fake_client_cert, fake_client_key
        )
        with pytest.raises(httpx.ReadError):
            async with httpx.AsyncClient(verify=ssl_context) as client:
                await client.get(f"{server}/test")
