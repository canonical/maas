# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from maasmcpserver.client import MAASClient
from maasmcpserver.config import MaasServerConfig
from maasmcpserver.errors import MAASPermissionError, MAASUnreachableError


@pytest.fixture
async def client():
    config = MaasServerConfig(maas_url="http://maas.example.com")
    maas_client = MAASClient(config, api_key="secret-token")
    try:
        yield maas_client
    finally:
        await maas_client.client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "method_name",
        "expected_method",
        "kwargs",
        "expected_json",
        "expected_params",
    ),
    [
        (
            "get",
            "GET",
            {
                "url_pattern": "/machines/{id}",
                "path_params": {"id": 1},
                "query_params": {"page": 2},
            },
            None,
            {"page": 2},
        ),
        (
            "post",
            "POST",
            {
                "url_pattern": "/machines/{id}",
                "path_params": {"id": 1},
                "body": {"name": "node-1"},
            },
            {"name": "node-1"},
            None,
        ),
        (
            "put",
            "PUT",
            {
                "url_pattern": "/machines/{id}",
                "path_params": {"id": 1},
                "body": {"hostname": "node-1"},
            },
            {"hostname": "node-1"},
            None,
        ),
        (
            "delete",
            "DELETE",
            {
                "url_pattern": "/machines/{id}",
                "path_params": {"id": 1},
            },
            None,
            None,
        ),
    ],
)
async def test_every_request_sets_authorization_header(
    client,
    method_name,
    expected_method,
    kwargs,
    expected_json,
    expected_params,
):
    response = httpx.Response(
        200,
        request=httpx.Request(expected_method, "http://maas.example.com"),
    )
    request_mock = AsyncMock(return_value=response)

    with (
        patch.object(client.client, "request", request_mock),
        patch("maasmcpserver.client.get_session_id", return_value="session-1"),
        patch("maasmcpserver.client.log_maas_request") as mock_log_request,
        patch("maasmcpserver.client.log_maas_response") as mock_log_response,
    ):
        result = await getattr(client, method_name)(**kwargs)

    assert result is response
    assert request_mock.await_count == 1
    request_mock.assert_awaited_once()

    call_kwargs = request_mock.await_args.kwargs
    assert call_kwargs["method"] == expected_method
    assert call_kwargs["url"] == "http://maas.example.com/machines/1"
    assert call_kwargs["headers"] == {"Authorization": "Bearer secret-token"}
    assert call_kwargs["json"] == expected_json
    assert call_kwargs["params"] == expected_params
    assert call_kwargs["timeout"].connect == 30

    mock_log_request.assert_called_once_with(
        "session-1", expected_method, "/machines/{id}"
    )
    mock_log_response.assert_called_once()
    assert mock_log_response.call_args.kwargs["http_status"] == 200


@pytest.mark.asyncio
async def test_timeout_raises_maas_unreachable_error(client):
    request_mock = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with (
        patch.object(client.client, "request", request_mock),
        patch("maasmcpserver.client.get_session_id", return_value="session-1"),
        patch("maasmcpserver.client.log_maas_request"),
        patch("maasmcpserver.client.log_maas_response") as mock_log_response,
    ):
        with pytest.raises(MAASUnreachableError) as exc_info:
            await client.get("/machines")

    assert exc_info.value.url_pattern == "/machines"
    assert exc_info.value.failure_mode == "timeout"
    assert request_mock.await_count == 1
    mock_log_response.assert_called_once()
    assert mock_log_response.call_args.kwargs["http_status"] == 0
    assert mock_log_response.call_args.kwargs["error"] == "maas_unreachable"


@pytest.mark.asyncio
async def test_connect_error_raises_maas_unreachable_error(client):
    request_mock = AsyncMock(
        side_effect=httpx.ConnectError("connection failed")
    )

    with (
        patch.object(client.client, "request", request_mock),
        patch("maasmcpserver.client.get_session_id", return_value="session-1"),
        patch("maasmcpserver.client.log_maas_request"),
        patch("maasmcpserver.client.log_maas_response"),
    ):
        with pytest.raises(MAASUnreachableError) as exc_info:
            await client.get("/machines")

    assert exc_info.value.url_pattern == "/machines"
    assert exc_info.value.failure_mode == "connection_refused"
    assert request_mock.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_http_permission_errors_raise_maas_permission_error(
    client, status_code
):
    response = httpx.Response(
        status_code,
        request=httpx.Request("GET", "http://maas.example.com/machines"),
    )
    request_mock = AsyncMock(return_value=response)

    with (
        patch.object(client.client, "request", request_mock),
        patch("maasmcpserver.client.get_session_id", return_value="session-1"),
        patch("maasmcpserver.client.log_maas_request"),
        patch("maasmcpserver.client.log_maas_response") as mock_log_response,
    ):
        with pytest.raises(MAASPermissionError) as exc_info:
            await client.get("/machines")

    assert exc_info.value.status_code == status_code
    assert request_mock.await_count == 1
    mock_log_response.assert_not_called()
