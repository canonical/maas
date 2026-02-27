# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import threading
from unittest.mock import MagicMock

import pytest

from maasserver.openfga import ThreadLocalFGACache


class TestFGACache:
    @pytest.fixture
    def client_mock(self):
        return MagicMock()

    @pytest.fixture
    def wrapped_client(self, client_mock):
        return ThreadLocalFGACache(client_mock)

    def test_calls_are_cached(self, wrapped_client, client_mock):
        client_mock.check.return_value = True

        wrapped_client.can_edit_machines("u1")
        wrapped_client.can_edit_machines("u1")

        assert client_mock.can_edit_machines.call_count == 1

    def test_cache_is_cleared(self, wrapped_client, client_mock):
        wrapped_client.can_edit_machines("u1")
        wrapped_client.clear_cache()
        wrapped_client.can_edit_machines("u1")

        assert client_mock.can_edit_machines.call_count == 2

    def test_thread_safety(self, wrapped_client, client_mock):
        """Ensures threads don't share their cache buckets."""

        def call_fga():
            wrapped_client.can_edit_machines("same_id")

        threads = [threading.Thread(target=call_fga) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread had an empty local cache, so 3 calls to the mock
        assert client_mock.can_edit_machines.call_count == 3
