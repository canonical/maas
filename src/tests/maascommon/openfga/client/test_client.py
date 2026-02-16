# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path

from aiohttp import web
import httpx
import pytest

from maascommon.enums.openfga import (
    OPENFGA_AUTHORIZATION_MODEL_ID,
    OPENFGA_STORE_ID,
)
from maascommon.openfga.client.client import OpenFGAClient


class MockFGAServer:
    def __init__(self):
        self.allowed = True
        self.last_payload = None
        self.status_code = 200

    async def check_handler(self, request):
        self.last_payload = await request.json()
        if self.status_code != 200:
            return web.Response(status=self.status_code)

        return web.json_response({"allowed": self.allowed, "resolution": ""})


@pytest.fixture
async def fga_server(tmp_path: Path):
    """Spin up a mock OpenFGA server using aiohttp that listens on a Unix socket. The server will record the last payload it received and return a configurable allowed value."""
    socket_path = str(tmp_path / "test-openfga.sock")
    handler_store = MockFGAServer()

    app = web.Application()
    app.router.add_post(
        f"/stores/{OPENFGA_STORE_ID}/check", handler_store.check_handler
    )

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.UnixSite(runner, socket_path)
    await site.start()

    yield handler_store, socket_path

    await runner.cleanup()


@pytest.fixture
async def fga_client(fga_server):
    """Fixture to create an instance of OpenFGAClient that connects to the mock server."""
    _, socket_path = fga_server
    return OpenFGAClient(unix_socket=socket_path)


@pytest.mark.asyncio
class TestOpenFGAClient:
    async def test_check_returns_allowed_true(self, fga_client, fga_server):
        server_state, _ = fga_server
        server_state.allowed = True

        tuple_key = {
            "user": "user:1",
            "relation": "can_edit_pools",
            "object": "maas:0",
        }
        result = await fga_client._check(tuple_key)

        assert result is True
        assert server_state.last_payload["tuple_key"] == tuple_key
        assert (
            server_state.last_payload["authorization_model_id"]
            == OPENFGA_AUTHORIZATION_MODEL_ID
        )

    async def test_check_returns_allowed_false(self, fga_client, fga_server):
        server_state, _ = fga_server
        server_state.allowed = False

        result = await fga_client.can_edit_pools("user-1")
        assert result is False

    @pytest.mark.parametrize(
        "method_name, args, expected_relation, expected_object",
        [
            ("can_edit_pools", ("u1",), "can_edit_pools", "maas:0"),
            ("can_view_pools", ("u1",), "can_view_pools", "maas:0"),
            (
                "can_edit_machines",
                ("u1", "p1"),
                "can_edit_machines",
                "pool:p1",
            ),
            (
                "can_deploy_machines",
                ("u1", "p1"),
                "can_deploy_machines",
                "pool:p1",
            ),
            (
                "can_view_machines",
                ("u1", "p1"),
                "can_view_machines",
                "pool:p1",
            ),
            (
                "can_view_global_entities",
                ("u1",),
                "can_view_global_entities",
                "maas:0",
            ),
            (
                "can_edit_global_entities",
                ("u1",),
                "can_edit_global_entities",
                "maas:0",
            ),
            (
                "can_view_permissions",
                ("u1",),
                "can_view_permissions",
                "maas:0",
            ),
            (
                "can_edit_permissions",
                ("u1",),
                "can_edit_permissions",
                "maas:0",
            ),
            (
                "can_view_configurations",
                ("u1",),
                "can_view_configurations",
                "maas:0",
            ),
            (
                "can_edit_configurations",
                ("u1",),
                "can_edit_configurations",
                "maas:0",
            ),
        ],
    )
    async def test_permission_methods(
        self,
        fga_client,
        fga_server,
        method_name,
        args,
        expected_relation,
        expected_object,
    ):
        server_state, _ = fga_server
        server_state.allowed = True

        method = getattr(fga_client, method_name)
        await method(*args)

        payload = server_state.last_payload
        assert payload["tuple_key"]["user"] == f"user:{args[0]}"
        assert payload["tuple_key"]["relation"] == expected_relation
        assert payload["tuple_key"]["object"] == expected_object
        assert (
            payload["authorization_model_id"] == OPENFGA_AUTHORIZATION_MODEL_ID
        )

    async def test_check_raises_for_status(self, fga_client, fga_server):
        server_state, _ = fga_server
        server_state.status_code = 500

        with pytest.raises(httpx.HTTPStatusError):
            await fga_client.can_edit_pools("u1")
