# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

from fastapi import Response
import pytest
from starlette.requests import Request
from starlette.types import ASGIApp

from maasapiserver.v3.middlewares.client_certificate import (
    RequireClientCertMiddleware,
)


@pytest.fixture
def middleware():
    return RequireClientCertMiddleware(Mock(ASGIApp))


@pytest.mark.asyncio
class TestRequireClientCertMiddleware:
    async def test_missing_client_cert_returns_403(self, middleware):
        mock_scope = {
            "type": "http",
            "method": "GET",
            "path": "/secure-endpoint",
            "headers": [],
            "extensions": {"tls": {"tls_used": True, "client_cert_chain": []}},
        }
        mock_request = Request(mock_scope)

        async def mock_call_next(request):
            return Response("OK")

        response = await middleware.dispatch(mock_request, mock_call_next)

        assert response.status_code == 403
        assert response.body == b'{"detail":"Client certificate required."}'

    async def test_valid_client_cert_allows_request(self, middleware):
        mock_scope = {
            "type": "http",
            "method": "GET",
            "path": "/secure-endpoint",
            "headers": [],
            "extensions": {
                "tls": {"client_cn": "01f09d32-f508-6064-bd1c-c025a58dd068"},
            },
        }
        mock_request = Request(mock_scope)

        async def call_next(request):
            return Response("OK")

        response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 200
        assert response.body == b"OK"

    async def test_missing_client_cert_for_agent_enroll_allows_request(
        self, middleware
    ):
        mock_request = type(
            "Request",
            (),
            {
                "scope": {
                    "headers": [],
                    "path": "/v3/agents:enroll",
                    "method": "POST",
                }
            },
        )
        mock_request_instance = mock_request()

        async def mock_call_next(request):
            return Response("OK")

        response = await middleware.dispatch(
            mock_request_instance, mock_call_next
        )

        assert response.status_code == 200
        assert response.body == b"OK"
