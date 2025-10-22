# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.responses import JSONResponse
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from maasapiserver.v3.middlewares.context import (
    ContextMiddleware,
    TRACE_ID_HEADER_KEY,
)


@pytest.fixture
def app():
    app = FastAPI()
    app.add_middleware(ContextMiddleware)

    @app.get("/ping")
    async def ping(request: Request):
        return JSONResponse({"trace_id": request.state.context.trace_id})

    return app


class TestContextMiddleware:
    def test_trace_id_is_generated_if_not_present(self, app):
        with patch(
            "maasapiserver.v3.middlewares.context.logger"
        ) as mock_logger:
            client = TestClient(app)
            resp = client.get("/ping")

        assert resp.status_code == 200

        trace_id = resp.headers.get(TRACE_ID_HEADER_KEY)
        assert trace_id, "ContextMiddleware should add trace_id header"

        assert resp.json()["trace_id"] == trace_id

        start_log = any(
            "Start processing request" in str(c.args[0])
            for c in mock_logger.info.call_args_list
        )
        end_log = any(
            "End processing request" in str(c.args[0])
            for c in mock_logger.info.call_args_list
        )
        assert start_log and end_log

    def test_trace_id_is_used_if_present(self, app):
        existing_trace = "existing-trace-id"

        client = TestClient(app)
        resp = client.get(
            "/ping", headers={TRACE_ID_HEADER_KEY: existing_trace}
        )

        assert resp.status_code == 200
        assert resp.json()["trace_id"] == existing_trace
        assert resp.headers[TRACE_ID_HEADER_KEY] == existing_trace

    def test_structlog_context_is_bound(self, app):
        with patch(
            "maasapiserver.v3.middlewares.context.structlog.contextvars"
        ) as mock_ctx:
            client = TestClient(app)
            resp = client.get("/ping")

        trace_id = resp.json()["trace_id"]

        mock_ctx.clear_contextvars.assert_called_once()
        mock_ctx.bind_contextvars.assert_called_once_with(trace_id=trace_id)

    def test_logger_captures_request_and_response(self, app):
        with patch(
            "maasapiserver.v3.middlewares.context.logger"
        ) as mock_logger:
            client = TestClient(app)
            resp = client.get(
                "/ping?foo=bar",
                headers={
                    "x-real-ip": "127.0.0.1",
                    "user-agent": "MockUserAgent",
                },
            )

        assert resp.status_code == 200

        start_call = mock_logger.info.call_args_list[0]
        assert "Start processing request" in start_call.args[0]
        assert start_call.kwargs["request_method"] == "GET"
        assert start_call.kwargs["request_path"] == "/ping"
        assert start_call.kwargs["request_query"] == "foo=bar"
        assert start_call.kwargs["request_remote_ip"] == "127.0.0.1"
        assert start_call.kwargs["useragent"] == "MockUserAgent"

        end_call = mock_logger.info.call_args_list[-1]
        assert "End processing request" in end_call.args[0]
        assert "status_code" in end_call.kwargs
        assert end_call.kwargs["status_code"] == 200
        assert "elapsed_time_seconds" in end_call.kwargs
