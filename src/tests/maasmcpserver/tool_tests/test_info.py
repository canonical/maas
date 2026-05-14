# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections.abc import Callable, Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.errors import MAASPermissionError, MAASUnreachableError
from maasmcpserver.tools import info

CONFIG_PATH = "/MAAS/a/v3/configurations/maas_name"
RACKS_PATH = "/MAAS/a/v3/racks"


def make_response(payload: object) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    return response


@pytest.fixture(autouse=True)
def set_maas_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAAS_URL", "http://maas.example.com")


@pytest.fixture(autouse=True)
def mock_context() -> Iterator[tuple[MagicMock, MagicMock]]:
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
            "maasmcpserver.tools.info.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.tools.info.get_session_id",
            return_value="test-session-id",
        ),
        patch(
            "maasmcpserver.tools.info.log_tool_received"
        ) as log_tool_received,
        patch("maasmcpserver.tools.info.log_tool_outcome") as log_tool_outcome,
    ):
        yield log_tool_received, log_tool_outcome


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

    info.register(FakeMCP(), config)
    return registered


@pytest.fixture
def mock_maas_client() -> Iterator[tuple[MagicMock, MagicMock]]:
    client = MagicMock()
    client.get = AsyncMock()
    client.client = MagicMock()
    client.client.aclose = AsyncMock()

    with patch(
        "maasmcpserver.tools.info.MAASClient",
        return_value=client,
    ) as client_class:
        yield client_class, client


@pytest.mark.asyncio
async def test_get_maas_info_fetches_configuration_and_racks_via_gather(
    config: MaasServerConfig,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    client_class, client = mock_maas_client
    log_tool_received, log_tool_outcome = mock_context
    config_response = make_response({"value": "my-maas"})
    racks_response = make_response(
        {
            "items": [
                {
                    "hostname": "rack-1",
                    "system_id": "xyz789",
                    "connection_state": "connected",
                }
            ]
        }
    )
    client.get.side_effect = [config_response, racks_response]

    original_gather = asyncio.gather
    gather_calls: list[tuple[object, ...]] = []

    async def recording_gather(*aws: object) -> tuple[MagicMock, MagicMock]:
        gather_calls.append(aws)
        return await original_gather(*aws)

    with patch(
        "maasmcpserver.tools.info.asyncio.gather",
        new=recording_gather,
    ):
        result = await registered_tools["get_maas_info"]()

    client_class.assert_called_once_with(config, "test-api-key")
    assert len(gather_calls) == 1
    assert len(gather_calls[0]) == 2
    assert client.get.await_count == 2
    assert [call.args[0] for call in client.get.await_args_list] == [
        CONFIG_PATH,
        RACKS_PATH,
    ]
    assert "**Deployment Name**: my-maas" in result
    assert "### Rack Controllers" in result
    assert "rack-1" in result
    assert "xyz789" in result
    assert "connected" in result
    assert "instance_uuid" not in result
    assert "region_controllers" not in result
    log_tool_received.assert_called_once_with(
        "test-session-id",
        "get_maas_info",
        {},
    )
    log_tool_outcome.assert_called_once_with(
        "test-session-id",
        "get_maas_info",
        "success",
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_maas_info_supports_flat_racks_payload(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = [
        make_response({"value": "my-maas"}),
        make_response(
            [
                {
                    "hostname": "rack-1",
                    "system_id": "xyz789",
                    "connection_state": "connected",
                }
            ]
        ),
    ]

    result = await registered_tools["get_maas_info"]()

    assert "rack-1" in result
    assert "xyz789" in result
    assert "connected" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_path", [CONFIG_PATH, RACKS_PATH])
async def test_get_maas_info_returns_maas_unreachable_error_string(
    failing_path: str,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    _, log_tool_outcome = mock_context
    config_response = make_response({"value": "my-maas"})
    racks_response = make_response({"items": []})

    async def fake_get(path: str, **_: object) -> MagicMock:
        if path == failing_path:
            raise MAASUnreachableError(path, "connection_refused")
        if path == CONFIG_PATH:
            return config_response
        return racks_response

    client.get.side_effect = fake_get

    result = await registered_tools["get_maas_info"]()

    assert result == (
        'Error (error_code: "maas_unreachable"): MAAS '
        f"unreachable (connection_refused) at {failing_path}"
    )
    log_tool_outcome.assert_called_once_with(
        "test-session-id",
        "get_maas_info",
        "error",
        "maas_unreachable",
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_maas_info_returns_permission_error_string(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    _, log_tool_outcome = mock_context
    client.get.side_effect = MAASPermissionError(403)

    result = await registered_tools["get_maas_info"]()

    assert result == (
        'Error (error_code: "permission_denied"): '
        "Permission denied (HTTP 403)."
    )
    log_tool_outcome.assert_called_once_with(
        "test-session-id",
        "get_maas_info",
        "error",
        "permission_denied",
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_maas_info_reports_when_no_rack_controllers_registered(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = [
        make_response({"value": "my-maas"}),
        make_response({"items": []}),
    ]

    result = await registered_tools["get_maas_info"]()

    assert "**Deployment Name**: my-maas" in result
    assert "No rack controllers registered." in result
    client.client.aclose.assert_awaited_once()
