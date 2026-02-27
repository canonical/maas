# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import httpx
import pytest

from maascommon.openfga.async_client import OpenFGAClient
from tests.maascommon.openfga.base import LIST_METHODS, PERMISSION_METHODS


@pytest.mark.asyncio
class TestOpenFGAClient:
    """Tests for the Asynchronous Client."""

    @pytest.fixture
    async def client(self, stub_openfga_server):
        _, socket_path = stub_openfga_server
        client = OpenFGAClient(unix_socket=socket_path)
        yield client
        await client.close()

    @pytest.mark.parametrize("method, args, rel, obj", PERMISSION_METHODS)
    async def test_all_permissions(
        self, client, stub_openfga_server, method, args, rel, obj
    ):
        server, _ = stub_openfga_server
        await getattr(client, method)(*args)
        assert server.last_payload["tuple_key"] == {
            "user": f"user:{args[0]}",
            "relation": rel,
            "object": obj,
        }

    @pytest.mark.parametrize("method, rel", LIST_METHODS)
    async def test_all_listings(
        self, client, stub_openfga_server, method, rel
    ):
        server, _ = stub_openfga_server
        server.list_objects_response = {"objects": ["pool:1", "pool:2"]}

        result = await getattr(client, method)("u1")

        assert result == [1, 2]
        assert server.last_payload["relation"] == rel
        assert server.last_payload["type"] == "pool"

    @pytest.mark.parametrize("status", [403, 500])
    async def test_async_raises_for_status(
        self, client, stub_openfga_server, status
    ):
        server, _ = stub_openfga_server
        server.status_code = status

        with pytest.raises(httpx.HTTPStatusError):
            await client.can_edit_machines("u1")

        with pytest.raises(httpx.HTTPStatusError):
            await client.list_pools_with_view_machines_access("u1")

    async def test_async_client_closes_properly(self):
        client = OpenFGAClient()
        await client.close()
        assert client.client.is_closed

    async def test_socket_path_is_set_from_env(self, monkeypatch):
        test_socket_path = "/tmp/test_socket"
        monkeypatch.setenv("MAAS_OPENFGA_HTTP_SOCKET_PATH", test_socket_path)
        client = OpenFGAClient()
        assert client.socket_path == test_socket_path
        await client.close()
