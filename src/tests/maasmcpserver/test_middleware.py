# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from unittest.mock import AsyncMock, patch
import uuid

import pytest

from maasmcpserver.middleware import (
    AuthMiddleware,
    get_api_key,
    get_session_id,
)


def make_scope(auth_header=None):
    headers = []
    if auth_header is not None:
        headers.append((b"authorization", auth_header.encode()))
    return {"type": "http", "headers": headers}


async def fake_receive():
    return {"type": "http.request", "body": b"", "more_body": False}


@pytest.mark.asyncio
async def test_no_auth_returns_401():
    responses = []

    async def send(event):
        responses.append(event)

    app = AsyncMock()
    middleware = AuthMiddleware(app)

    with (
        patch("maasmcpserver.middleware.log_session_opened") as mock_opened,
        patch("maasmcpserver.middleware.log_session_closed") as mock_closed,
    ):
        await middleware(make_scope(), fake_receive, send)

    assert responses[0]["status"] == 401
    assert responses[1]["body"] == b'{"error":"Unauthorized"}'
    app.assert_not_awaited()
    mock_opened.assert_not_called()
    mock_closed.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_header", ["Basic token", "Bearer "])
async def test_invalid_auth_returns_401(auth_header):
    responses = []

    async def send(event):
        responses.append(event)

    app = AsyncMock()
    middleware = AuthMiddleware(app)

    with (
        patch("maasmcpserver.middleware.log_session_opened") as mock_opened,
        patch("maasmcpserver.middleware.log_session_closed") as mock_closed,
    ):
        await middleware(make_scope(auth_header), fake_receive, send)

    assert responses[0]["status"] == 401
    assert responses[1]["body"] == b'{"error":"Unauthorized"}'
    app.assert_not_awaited()
    mock_opened.assert_not_called()
    mock_closed.assert_not_called()


@pytest.mark.asyncio
async def test_valid_bearer_sets_context_and_logs_session_lifecycle():
    session_id = uuid.UUID("00000000-0000-0000-0000-000000000123")

    async def app(scope, receive, send):
        assert get_session_id() == str(session_id)
        assert get_api_key() == "token-1"

    middleware = AuthMiddleware(AsyncMock(side_effect=app))

    with (
        patch(
            "maasmcpserver.middleware.uuid.uuid4",
            return_value=session_id,
        ),
        patch("maasmcpserver.middleware.log_session_opened") as mock_opened,
        patch("maasmcpserver.middleware.log_session_closed") as mock_closed,
    ):
        await middleware(
            make_scope("Bearer token-1"), fake_receive, AsyncMock()
        )

    mock_opened.assert_called_once_with(str(session_id), "token-1")
    mock_closed.assert_called_once_with(str(session_id))
    assert get_session_id() == ""
    assert get_api_key() == ""


@pytest.mark.asyncio
async def test_contextvars_are_isolated_between_concurrent_requests():
    observed = {}

    async def app(scope, receive, send):
        first = (get_session_id(), get_api_key())
        await asyncio.sleep(0)
        second = (get_session_id(), get_api_key())
        observed[get_api_key()] = (first, second)

    middleware = AuthMiddleware(AsyncMock(side_effect=app))
    session_one = uuid.UUID("00000000-0000-0000-0000-000000000101")
    session_two = uuid.UUID("00000000-0000-0000-0000-000000000202")

    with (
        patch(
            "maasmcpserver.middleware.uuid.uuid4",
            side_effect=[session_one, session_two],
        ),
        patch("maasmcpserver.middleware.log_session_opened"),
        patch("maasmcpserver.middleware.log_session_closed"),
    ):
        await asyncio.gather(
            middleware(
                make_scope("Bearer token-a"), fake_receive, AsyncMock()
            ),
            middleware(
                make_scope("Bearer token-b"), fake_receive, AsyncMock()
            ),
        )

    assert set(observed) == {"token-a", "token-b"}
    assert observed["token-a"] == (
        (str(session_one), "token-a"),
        (str(session_one), "token-a"),
    )
    assert observed["token-b"] == (
        (str(session_two), "token-b"),
        (str(session_two), "token-b"),
    )
