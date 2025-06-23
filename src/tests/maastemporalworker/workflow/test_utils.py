# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import asyncio
from unittest.mock import Mock

import pytest

from maastemporalworker.workflow.utils import async_retry


@pytest.mark.asyncio
class TestAsyncRetry:
    def test_async_retry_retries_async_function(self):
        mock = Mock()

        @async_retry(retries=2, backoff_ms=1)
        async def _fn():
            mock.fn()
            raise Exception()

        try:
            asyncio.run(_fn())
        except Exception:
            pass

        mock.fn.assert_called()
        assert mock.fn.call_count == 2

    def test_async_retry_does_not_retry_success(self):
        mock = Mock()

        @async_retry(retries=2, backoff_ms=1)
        async def _fn():
            mock.fn()

        asyncio.run(_fn())

        mock.fn.assert_called()
        assert mock.fn.call_count == 1
