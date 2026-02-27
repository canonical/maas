# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio

import httpx
import pytest

from maascommon.openfga.sync_client import SyncOpenFGAClient
from tests.maascommon.openfga.base import LIST_METHODS, PERMISSION_METHODS


@pytest.mark.asyncio
class TestSyncOpenFGAClient:
    """Tests for the Synchronous Client."""

    class MockUser:
        def __init__(self, user_id):
            self.id = user_id

    @pytest.fixture
    async def client(self, stub_openfga_server):
        _, socket_path = stub_openfga_server
        client = SyncOpenFGAClient(unix_socket=socket_path)
        yield client
        client.close()

    @pytest.mark.parametrize("method, args, rel, obj", PERMISSION_METHODS)
    async def test_all_permissions_sync(
        self, client, stub_openfga_server, method, args, rel, obj
    ):
        server, _ = stub_openfga_server
        user = self.MockUser(args[0])
        method = getattr(client, method)

        # Replace the first argument with the MockUser (django User) instance
        await asyncio.to_thread(method, user, *args[1:])

        assert server.last_payload["tuple_key"] == {
            "user": f"user:{args[0]}",
            "relation": rel,
            "object": obj,
        }

    @pytest.mark.parametrize("method, rel", LIST_METHODS)
    async def test_all_listings_sync(
        self, client, stub_openfga_server, method, rel
    ):
        server, _ = stub_openfga_server
        server.list_objects_response = {"objects": ["pool:123"]}
        method = getattr(client, method)

        result = await asyncio.to_thread(method, self.MockUser("admin"))

        assert result == [123]
        assert server.last_payload["relation"] == rel
        assert server.last_payload["user"] == "user:admin"

    @pytest.mark.parametrize("status", [401, 404, 503])
    async def test_sync_raises_for_status(
        self, client, stub_openfga_server, status
    ):
        server, _ = stub_openfga_server
        server.status_code = status
        user = self.MockUser("tester")

        # The exception bubbles up through the anyio thread worker
        with pytest.raises(httpx.HTTPStatusError) as excinfo:
            await asyncio.to_thread(client.can_edit_machines, user)

        assert excinfo.value.response.status_code == status

    async def test_client_closes_properly(self):
        client = SyncOpenFGAClient()
        client.close()
        assert client.client.is_closed

    async def test_socket_path_is_set_from_env(
        self, stub_openfga_server, monkeypatch
    ):
        _, socket_path = stub_openfga_server
        monkeypatch.setenv("MAAS_OPENFGA_HTTP_SOCKET_PATH", socket_path)
        client = SyncOpenFGAClient()
        assert client.socket_path == socket_path
        client.close()
