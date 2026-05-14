# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Callable, Iterator
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from maasmcpserver.config import MaasServerConfig
from maasmcpserver.errors import MAASPermissionError
from maasmcpserver.tools import diagnostics

EVENTS_PAYLOAD = {
    "items": [
        {
            "id": 1,
            "created": "2024-01-01T10:00:00Z",
            "type": "commissioning",
            "description": "Machine commissioning started",
            "username": "admin",
            "level": "INFO",
        },
        {
            "id": 2,
            "created": "2024-01-01T09:00:00Z",
            "type": "deploy",
            "description": "Machine deployed",
            "username": None,
            "level": "WARNING",
        },
    ]
}

SCRIPT_RESULTS_PAYLOAD = {
    "items": [
        {
            "id": 1,
            "name": "commissioning",
            "status": "passed",
            "exit_status": 0,
            "output": "All checks passed",
            "started": "2024-01-01T09:00:00Z",
            "ended": "2024-01-01T09:05:00Z",
        }
    ]
}


class FrozenDateTime(datetime):
    @classmethod
    def now(cls, tz: timezone | None = None) -> "FrozenDateTime":
        frozen = cls(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        if tz is None:
            return frozen
        return frozen.astimezone(tz)


def make_response(data: object) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = data
    mock.status_code = 200
    return mock


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
            "maasmcpserver.tools.diagnostics.get_api_key",
            return_value="test-api-key",
        ),
        patch(
            "maasmcpserver.tools.diagnostics.get_session_id",
            return_value="test-session-id",
        ),
        patch(
            "maasmcpserver.tools.diagnostics.log_tool_received",
        ) as log_tool_received,
        patch(
            "maasmcpserver.tools.diagnostics.log_tool_outcome",
        ) as log_tool_outcome,
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

    diagnostics.register(FakeMCP(), config)
    return registered


@pytest.fixture
def mock_maas_client() -> Iterator[tuple[MagicMock, MagicMock]]:
    client = MagicMock()
    client.get = AsyncMock()
    client.client = MagicMock()
    client.client.aclose = AsyncMock()

    with patch(
        "maasmcpserver.tools.diagnostics.MAASClient",
        return_value=client,
    ) as client_class:
        yield client_class, client


@pytest.mark.asyncio
async def test_get_machine_events_resolves_hostname_then_requests_events(
    config: MaasServerConfig,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    client_class, client = mock_maas_client
    log_tool_received, log_tool_outcome = mock_context
    client.get.side_effect = [
        make_response({"items": [{"system_id": "abc123"}]}),
        make_response(EVENTS_PAYLOAD),
    ]

    result = await registered_tools["get_machine_events"](identifier="node-1")

    client_class.assert_called_once_with(config, "test-api-key")
    assert client.get.await_count == 2
    first_call = client.get.await_args_list[0]
    second_call = client.get.await_args_list[1]
    assert first_call.args == ("/MAAS/a/v3/machines",)
    assert first_call.kwargs == {"query_params": {"hostname": "node-1"}}
    assert second_call.args == ("/MAAS/a/v3/events",)
    assert second_call.kwargs == {"query_params": {"system_id": "abc123"}}
    assert result.index("2024-01-01T09:00:00Z") < result.index(
        "2024-01-01T10:00:00Z"
    )
    log_tool_received.assert_called_once_with(
        "test-session-id",
        "get_machine_events",
        {"identifier": "node-1", "since_hours": None},
    )
    log_tool_outcome.assert_called_once_with(
        "test-session-id", "get_machine_events", "success"
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_machine_events_filters_since_hours_client_side(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.side_effect = [
        make_response({"items": [{"system_id": "abc123"}]}),
        make_response(
            {
                "items": [
                    {
                        "id": 1,
                        "created": "2024-01-01T10:30:00Z",
                        "type": "commissioning",
                        "description": "Recent event",
                        "username": "admin",
                        "level": "INFO",
                    },
                    {
                        "id": 2,
                        "created": "2024-01-01T08:59:59Z",
                        "type": "deploy",
                        "description": "Old event",
                        "username": None,
                        "level": "WARNING",
                    },
                ]
            }
        ),
    ]

    with patch("maasmcpserver.tools.diagnostics.datetime", FrozenDateTime):
        result = await registered_tools["get_machine_events"](
            identifier="node-1",
            since_hours=2,
        )

    assert "Recent event" in result
    assert "Old event" not in result
    events_call = client.get.await_args_list[1]
    assert events_call.kwargs == {"query_params": {"system_id": "abc123"}}
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_script_results_requests_machine_script_results(
    config: MaasServerConfig,
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    client_class, client = mock_maas_client
    client.get.side_effect = [
        make_response({"items": [{"system_id": "abc123"}]}),
        make_response(SCRIPT_RESULTS_PAYLOAD),
    ]

    result = await registered_tools["get_script_results"](
        identifier="node-1",
        script_type="commissioning",
    )

    client_class.assert_called_once_with(config, "test-api-key")
    assert client.get.await_count == 2
    first_call = client.get.await_args_list[0]
    second_call = client.get.await_args_list[1]
    assert first_call.args == ("/MAAS/a/v3/machines",)
    assert first_call.kwargs == {"query_params": {"hostname": "node-1"}}
    assert second_call.args == (
        "/MAAS/a/v3/machines/{system_id}/script_results",
    )
    assert second_call.kwargs == {
        "path_params": {"system_id": "abc123"},
        "query_params": {"script_type": "commissioning"},
    }
    assert "## Script Results: node-1 (abc123)" in result
    assert "### commissioning" in result
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_script_results_returns_permission_error_string(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    _, log_tool_outcome = mock_context
    client.get.side_effect = MAASPermissionError(403)

    result = await registered_tools["get_script_results"](identifier="node-1")

    assert result == (
        'Error (error_code: "permission_denied"): '
        "Permission denied (HTTP 403)."
    )
    log_tool_outcome.assert_called_once_with(
        "test-session-id",
        "get_script_results",
        "error",
        "permission_denied",
    )
    client.client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_machine_events_returns_descriptive_error_when_missing(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
    mock_context: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    _, log_tool_outcome = mock_context
    client.get.return_value = make_response({"items": []})

    result = await registered_tools["get_machine_events"](identifier="node-1")

    assert result == (
        "Error (error_code: \"not_found\"): Machine not found: 'node-1'"
    )
    log_tool_outcome.assert_called_once_with(
        "test-session-id",
        "get_machine_events",
        "error",
        "not_found",
    )
    client.client.aclose.assert_awaited_once()


GLOBAL_EVENTS_PAYLOAD = {
    "total": 2,
    "items": [
        {
            "id": 10,
            "created": "2026-05-14T10:00:00Z",
            "type": {
                "name": "NODE_COMMISSIONING",
                "level": "INFO",
                "description": "Node commissioning",
            },
            "node_hostname": "node-1",
            "node_system_id": "abc123",
            "owner": "admin",
            "action": "Commissioned",
            "description": "Machine commissioning started",
            "user_agent": "maas",
        },
        {
            "id": 11,
            "created": "2026-05-14T11:00:00Z",
            "type": {
                "name": "NODE_DEPLOYED",
                "level": "AUDIT",
                "description": "Node deployed",
            },
            "node_hostname": "node-2",
            "node_system_id": "def456",
            "owner": "user1",
            "action": "Deployed",
            "description": "Machine deployed successfully",
            "user_agent": "maas-cli",
        },
    ],
}


@pytest.mark.asyncio
async def test_list_events_returns_table_of_all_events(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(GLOBAL_EVENTS_PAYLOAD)

    result = await registered_tools["list_events"]()

    client.get.assert_awaited_once_with(
        "/MAAS/a/v3/events",
        query_params={"page": 1, "size": 100},
    )
    assert "## MAAS Events" in result
    assert "Total: 2" in result
    assert "node-1" in result
    assert "node-2" in result
    assert "INFO" in result
    assert "AUDIT" in result
    assert "Machine commissioning started" in result


@pytest.mark.asyncio
async def test_list_events_passes_system_id_filter(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response(
        {"total": 1, "items": [GLOBAL_EVENTS_PAYLOAD["items"][0]]}
    )

    result = await registered_tools["list_events"](
        system_ids=["abc123"], page=1, page_size=50
    )

    client.get.assert_awaited_once_with(
        "/MAAS/a/v3/events",
        query_params={"page": 1, "size": 50, "system_id": ["abc123"]},
    )
    assert "system_ids: abc123" in result
    assert "node-1" in result


@pytest.mark.asyncio
async def test_list_events_returns_empty_message_when_no_events(
    registered_tools: dict[str, Callable[..., object]],
    mock_maas_client: tuple[MagicMock, MagicMock],
) -> None:
    _, client = mock_maas_client
    client.get.return_value = make_response({"total": 0, "items": []})

    result = await registered_tools["list_events"]()

    assert "No events found." in result
