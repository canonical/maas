# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
from httpx import Request, Response
import pytest

from maastemporalworker.workflow.api_client import MAASAPIClient


@pytest.fixture
def dummy_token():
    return "key:secret:consumer_key"


@pytest.fixture
def client(dummy_token):
    return MAASAPIClient(
        url="http://example.com", token=dummy_token, user_agent="MAAS"
    )


class TestMAASAPIClient:
    @patch(
        "maastemporalworker.workflow.api_client.worker_socket_paths",
        return_value=["/tmp/socket1", "/tmp/socket2"],
    )
    @patch(
        "maastemporalworker.workflow.api_client.random.choice",
        return_value="/tmp/socket1",
    )
    @patch("maastemporalworker.workflow.api_client.httpx.AsyncHTTPTransport")
    @patch("maastemporalworker.workflow.api_client.httpx.AsyncClient")
    def test_create_unix_client(
        self,
        mock_async_client,
        mock_transport,
        mock_choice,
        mock_paths,
        dummy_token,
    ):
        mock_transport_instance = MagicMock()
        mock_transport.return_value = mock_transport_instance

        MAASAPIClient("http://example.com", dummy_token, user_agent="MAAS")

        mock_transport.assert_called_once_with(uds="/tmp/socket1")
        mock_async_client.assert_called_once()
        _, kwargs = mock_async_client.call_args
        assert kwargs["headers"]["User-Agent"] == "MAAS"

    @patch("maastemporalworker.workflow.api_client.httpx.AsyncClient")
    def test_create_client_with_proxy(self, mock_async_client, dummy_token):
        client = MAASAPIClient(
            "http://example.com", dummy_token, user_agent="MAAS"
        )
        proxy = "http://proxy.example.com"

        client.make_client(proxy)

        _, kwargs = mock_async_client.call_args
        assert kwargs["proxy"] == proxy
        assert kwargs["headers"]["User-Agent"] == "MAAS"
        assert kwargs["verify"] is False
        assert isinstance(kwargs["timeout"], httpx.Timeout)

    @patch("maastemporalworker.workflow.api_client.httpx.AsyncClient")
    def test_create_client_empty_proxy(self, mock_async_client, dummy_token):
        client = MAASAPIClient(
            "http://example.com", dummy_token, user_agent="MAAS"
        )

        client.make_client("")

        _, kwargs = mock_async_client.call_args
        assert kwargs["proxy"] is None

    @pytest.mark.asyncio
    @patch("maastemporalworker.workflow.api_client.MAASOAuth")
    async def test_request_async_success(self, mock_oauth, dummy_token):
        mock_oauth_instance = mock_oauth.return_value
        mock_oauth_instance.sign_request = MagicMock()

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {"result": "ok"}

        client = MAASAPIClient(
            "http://example.com", dummy_token, user_agent="MAAS"
        )
        client._unix_client = AsyncMock()
        client._unix_client.request.return_value = mock_response

        result = await client.request_async(
            method="GET", url="http://example.com/api", params={"q": 1}
        )

        client._unix_client.request.assert_awaited_once_with(
            "GET",
            "http://example.com/api",
            params={"q": 1},
            data=None,
            headers={},
        )
        mock_oauth_instance.sign_request.assert_called_once()
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    @patch("maastemporalworker.workflow.api_client.MAASOAuth")
    async def test_request_async_raises_http_error(
        self, mock_oauth, dummy_token
    ):
        mock_oauth_instance = mock_oauth.return_value
        mock_oauth_instance.sign_request = MagicMock()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=Mock(Request), response=Mock(Response)
        )

        client = MAASAPIClient("http://example.com", dummy_token)
        client._unix_client = AsyncMock()
        client._unix_client.request.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            await client.request_async("GET", "http://example.com/api")
