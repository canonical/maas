# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `discourse_api` module."""

from unittest.mock import patch

from .helpers import load_module, TOOLS_DIR


class FakeResponse:
    """Fake HTTP response for testing."""

    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json = json_data or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise RuntimeError("http error")


class FakeSession:
    """Fake requests session for testing."""

    def __init__(self, responses):
        self.headers = {}
        self._responses = list(responses)
        self.requested = []

    def get(self, url):
        self.requested.append(("GET", url))
        return self._responses.pop(0)

    def post(self, url, json):
        self.requested.append(("POST", url, json))
        return FakeResponse(200, {"ok": True})

    def put(self, url, json):
        self.requested.append(("PUT", url, json))
        return FakeResponse(200, {"ok": True})


def test_call_api_handles_rate_limit():
    """Test that rate limit responses (429) are handled correctly."""
    mod = load_module("_disc_api", TOOLS_DIR / "discourse_api.py")

    seq = [
        FakeResponse(429, {"wait_seconds": 0}),
        FakeResponse(200, {"ok": True}),
    ]
    sess = FakeSession(seq)

    with patch.object(mod.requests, "Session", return_value=sess):
        api = mod.DiscourseAPI({"base_url": "https://x", "api_key": "k"})
        data = api.call_api("/t/1.json")
        assert data == {"ok": True}
        assert sess.requested[0][0] == "GET"


def test_get_markdown():
    """Test retrieving markdown content from a topic."""
    mod = load_module("_disc_api2", TOOLS_DIR / "discourse_api.py")

    api = mod.DiscourseAPI({"base_url": "https://x", "api_key": "k"})

    def fake_call(endpoint):
        if endpoint.startswith("/t/"):
            return {"post_stream": {"posts": [{"id": 42}]}}
        if endpoint.startswith("/posts/"):
            return {"raw": "hello"}
        raise AssertionError("unexpected")

    api.call_api = fake_call
    assert api.get_markdown(99) == "hello"


def test_update_topic_content():
    """Test updating topic content via PUT request."""
    mod = load_module("_disc_api7", TOOLS_DIR / "discourse_api.py")

    sess = FakeSession(
        [
            FakeResponse(200, {"post_stream": {"posts": [{"id": 5}]}}),
            FakeResponse(200, {"raw": "old"}),
        ]
    )

    with patch.object(mod.requests, "Session", return_value=sess):
        api = mod.DiscourseAPI({"base_url": "https://x", "api_key": "k"})

        status = api.update_topic_content(1, "new")
        assert status == 200
        assert any(req[0] == "PUT" for req in sess.requested)
