# Copyright 2026 Canonical Ltd.  This software is licensed under the GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.tools import fleet

MACHINE_PAYLOAD = {
    "system_id": "abc123",
    "hostname": "node-1",
    "status_name": "Ready",
    "zone": {"name": "default"},
    "pool": {"name": "default"},
    "architecture": "amd64/generic",
    "cpu_count": 4,
    "memory_mb": 8192,
    "owner": None,
    "power_state": "on",
    "tags": [],
}


def _response(payload: object) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


@pytest.fixture(autouse=True)
def set_maas_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAAS_URL", "http://maas.example.com")


@pytest.fixture(autouse=True)
def mock_middleware_context() -> Iterator[None]:
    with (
        patch(
            "maasmcpserver.middleware.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.middleware.get_session_id",
            return_value="test-session-id",
        ),
        patch(
            "maasmcpserver.tools.fleet.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.tools.fleet.get_session_id",
            return_value="test-session-id",
        ),
    ):
        yield


@pytest.fixture
def config() -> MaasServerConfig:
    return MaasServerConfig()


@pytest.fixture
def registered_tools(
    config: MaasServerConfig,
) -> dict[str, Callable[..., object]]:
    registered: dict[str, Callable[..., object]] = {}

    class FakeMCP:
        def tool(
            self,
            **_: object,
        ) -> Callable[[Callable[..., object]], Callable[..., object]]:
            def decorator(
                func: Callable[..., object],
            ) -> Callable[..., object]:
                registered[func.__name__] = func
                return func

            return decorator

    fleet.register(FakeMCP(), config)
    return registered


@pytest.fixture
def mock_maas_client() -> Iterator[tuple[MagicMock, MagicMock]]:
    client = MagicMock()
    client.get = AsyncMock()
    client.client = MagicMock()
    client.client.aclose = AsyncMock()

    with patch(
        "maasmcpserver.tools.fleet.MAASClient",
        return_value=client,
    ) as client_class:
        yield client_class, client


@pytest.mark.asyncio
async def test_list_machines_forwards_filters_and_pagination(
    config: MaasServerConfig,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    client_class, client = mock_maas_client
    client.get.return_value = _response(
        {"items": [MACHINE_PAYLOAD], "total": 1}
    )

    result = await registered_tools["list_machines"](
        status="Ready",
        zone="default",
        pool="default",
        architecture="amd64/generic",
        tags="gpu,fast",
        owner="alice",
        power_state="on",
        page=2,
        page_size=25,
    )

    client_class.assert_called_once_with(config, "test-api-key")
    client.get.assert_awaited_once_with(
        "/MAAS/a/v3/machines",
        query_params={
            "status": "Ready",
            "zone": "default",
            "pool": "default",
            "architecture": "amd64/generic",
            "tags": "gpu,fast",
            "owner": "alice",
            "power_state": "on",
            "page": 2,
            "size": 25,
        },
    )
    assert "page_size" not in client.get.await_args.kwargs["query_params"]
    assert "|" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_machines_returns_message_when_empty(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = _response({"items": [], "total": 0})

    result = await registered_tools["list_machines"]()

    assert result == "No machines found."
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_machine_resolves_hostname_then_loads_details(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = [
        _response({"items": [{"system_id": "abc123"}], "total": 1}),
        _response(MACHINE_PAYLOAD),
        _response(
            {
                "items": [
                    {
                        "id": 1,
                        "name": "eth0",
                        "type": "physical",
                        "mac_address": "00:11:22:33:44:55",
                        "enabled": True,
                        "ip_addresses": ["192.168.1.10"],
                    }
                ],
                "total": 1,
            }
        ),
    ]

    result = await registered_tools["get_machine"]("node-1")

    assert client.get.await_count == 3
    first_call = client.get.await_args_list[0]
    second_call = client.get.await_args_list[1]
    third_call = client.get.await_args_list[2]

    assert first_call.args == ("/MAAS/a/v3/machines",)
    assert first_call.kwargs == {"query_params": {"hostname": "node-1"}}
    assert second_call.args == ("/MAAS/a/v3/machines/{system_id}",)
    assert second_call.kwargs == {"path_params": {"system_id": "abc123"}}
    assert third_call.args == ("/MAAS/a/v3/machines/{system_id}/interfaces",)
    assert third_call.kwargs == {"path_params": {"system_id": "abc123"}}
    assert "# Machine: node-1" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_machine_power_state_extracts_power_state(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = [
        _response({"items": [{"system_id": "abc123"}], "total": 1}),
        _response(MACHINE_PAYLOAD),
    ]

    result = await registered_tools["get_machine_power_state"]("node-1")

    assert result == "node-1: power state is on"
    client.client.aclose.assert_awaited_once()
