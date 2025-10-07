# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from unittest.mock import Mock, patch
import uuid

import pytest

from maascommon.tracing import (
    get_or_set_trace_id,
    get_trace_id,
    set_trace_id,
    TRACE_ID,
)


class TestTracing:
    def test_get_trace_id_default(self):
        assert get_trace_id() == "", (
            "The default trace id should be empty string."
        )

    def test_get_trace_id_with_value(self):
        TRACE_ID.set("test")
        assert get_trace_id() == "test"

    def test_set_trace_id_sets_value(self):
        trace_id = "custom-trace-123"
        set_trace_id(trace_id)
        assert TRACE_ID.get() == trace_id

    def test_get_or_set_trace_id_returns_existing(self):
        trace_id = "existing-trace-456"
        TRACE_ID.set(trace_id)

        result = get_or_set_trace_id()
        assert result == trace_id, "Should return the existing trace ID"

    @patch("uuid.uuid4")
    def test_get_or_set_trace_id_generates_new_if_empty(self, patch_uuid):
        TRACE_ID.set("")

        fake_uuid = "fakeuuid1234567890"

        uuid_hex_mock = Mock(uuid.UUID)
        uuid_hex_mock.hex = fake_uuid
        patch_uuid.return_value = uuid_hex_mock

        result = get_or_set_trace_id()

        assert result == fake_uuid, "Should generate a new trace ID"
        assert TRACE_ID.get() == fake_uuid, (
            "TRACE_ID context variable should be updated"
        )

    def test_get_or_set_trace_id_returns_same_on_subsequent_calls(self):
        TRACE_ID.set("")  # the default

        first_call = get_or_set_trace_id()
        second_call = get_or_set_trace_id()

        assert first_call == second_call, (
            "Subsequent calls should return the same trace ID"
        )

    @pytest.mark.asyncio
    async def test_each_task_should_have_its_own_trace_id(self):
        TRACE_ID.set("")

        async def work():
            return get_or_set_trace_id()

        first_result = await asyncio.create_task(work())
        second_result = await asyncio.create_task(work())

        assert first_result != second_result, (
            "Each task should have its own trace ID"
        )
