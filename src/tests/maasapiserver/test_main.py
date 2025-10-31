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


def _get_test_file(filename: str) -> Path:
    return Path(__file__).parent / "data_test_main" / filename


@pytest.fixture
def ca_cert():
    yield _get_test_file("ca.pem")


@pytest.fixture
async def server(db, ca_cert):
    server_cert = _get_test_file("server.pem")
    server_key = _get_test_file("server.key")

    app = craft_internal_app(
        db,
        server_config=ServerConfig(
            host="localhost",
            port=9443,
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
        "/agents:enroll", endpoint=index, methods=["POST"]
    )

    server = app.server

    # inspired from https://github.com/Kludex/uvicorn/blob/b8e65e49bfadf6d5ea30e56d0cd9f47329de606c/tests/utils.py#L9-L18
    cancel_handle = asyncio.ensure_future(server.serve())
    await asyncio.sleep(0.1)
    try:
        yield server
    finally:
        await server.shutdown()
        cancel_handle.cancel()


@pytest.mark.asyncio
class TestMTLSInternalServer:
    async def test_mtls_with_signed_client_certs(self, server, ca_cert):
        client_cert = _get_test_file("client.pem")
        client_key = _get_test_file("client.key")

        async with httpx.AsyncClient(
            verify=str(ca_cert),
            cert=(str(client_cert), str(client_key)),
        ) as client:
            r1 = await client.get("https://localhost:9443/test")
        assert r1.status_code == 200
        data1 = r1.json()
        tls_ext1 = data1["tls"]
        assert tls_ext1["tls_used"] is True
        assert tls_ext1["client_cn"] == "Good Agent"
        assert len(tls_ext1["client_cert_chain"]) == 1
        assert "tls_version" in tls_ext1

    async def test_mtls_agent_enrol_endpoint(self, server, ca_cert):
        async with httpx.AsyncClient(verify=str(ca_cert)) as client:
            r2 = await client.post("https://localhost:9443/agents:enroll")
        assert r2.status_code == 200
        data2 = r2.json()
        tls_ext2 = data2["tls"]
        assert tls_ext2["tls_used"] is True
        assert tls_ext2["client_cert_chain"] == []
        assert "tls_version" in tls_ext2

    async def test_mtls_client_certificate_is_required(self, server, ca_cert):
        async with httpx.AsyncClient(verify=str(ca_cert)) as client:
            r2 = await client.post("https://localhost:9443/test")
        assert r2.status_code == 403

    async def test_mtls_with_wrong_ca(self, server):
        fake_ca_cert = _get_test_file("fake_ca.pem")
        client_cert = _get_test_file("client.pem")
        client_key = _get_test_file("client.key")

        with pytest.raises(
            (httpx.ConnectError, ssl.SSLError, ssl.SSLCertVerificationError)
        ):
            async with httpx.AsyncClient(
                verify=str(fake_ca_cert),
                cert=(str(client_cert), str(client_key)),
            ) as client:
                await client.get("https://localhost:9443/test")

    async def test_mtls_with_wrong_key(self, server, ca_cert):
        client_cert = _get_test_file("client.pem")
        fake_client_key = _get_test_file("fake_client.key")

        with pytest.raises(ssl.SSLError):
            async with httpx.AsyncClient(
                verify=str(ca_cert),
                cert=(str(client_cert), str(fake_client_key)),
            ) as client:
                await client.get("https://localhost:9443/test")

    async def test_mtls_with_wrong_cert(self, server, ca_cert):
        fake_client_cert = _get_test_file("fake_client.pem")
        client_key = _get_test_file("fake_client.key")

        with pytest.raises(httpx.ReadError):
            async with httpx.AsyncClient(
                verify=str(ca_cert),
                cert=(str(fake_client_cert), str(client_key)),
            ) as client:
                await client.get("https://localhost:9443/test")

    async def test_mtls_with_fake_client_certificate(self, server, ca_cert):
        fake_client_cert = _get_test_file("fake_client.pem")
        fake_client_key = _get_test_file("fake_client.key")

        with pytest.raises(httpx.ReadError):
            async with httpx.AsyncClient(
                verify=str(ca_cert),
                cert=(str(fake_client_cert), str(fake_client_key)),
            ) as client:
                await client.get("https://localhost:9443/test")
