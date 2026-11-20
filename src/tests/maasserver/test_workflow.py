# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the workflow module."""

from unittest.mock import AsyncMock, MagicMock

from temporalio.service import RPCError, RPCStatusCode
from twisted.internet.defer import inlineCallbacks

from maasserver import workflow as workflow_module
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase

wait_for_reactor = wait_for()


class TestStopWorkflow(MAASTestCase):
    """Tests for stop_workflow function."""

    @wait_for_reactor
    @inlineCallbacks
    def test_stops_workflow_successfully(self):
        """Test that stop_workflow succeeds when workflow exists."""
        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.cancel = AsyncMock()
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        self.patch(
            workflow_module,
            "get_client_async",
            AsyncMock(return_value=mock_client),
        )

        # Should not raise any exception
        yield workflow_module.stop_workflow("deploy:test-id")

        mock_handle.cancel.assert_called_once()

    @wait_for_reactor
    @inlineCallbacks
    def test_handles_workflow_not_found(self):
        """Test that stop_workflow handles NOT_FOUND status gracefully."""
        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.cancel = AsyncMock(
            side_effect=RPCError(
                "workflow not found for ID: deploy:test-id",
                RPCStatusCode.NOT_FOUND,
                b"",
            )
        )
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        self.patch(
            workflow_module,
            "get_client_async",
            AsyncMock(return_value=mock_client),
        )

        # Should not raise - workflow already gone
        yield workflow_module.stop_workflow("deploy:test-id")

        mock_handle.cancel.assert_called_once()

    @wait_for_reactor
    @inlineCallbacks
    def test_propagates_other_rpc_errors(self):
        """Test that stop_workflow re-raises other RPCErrors."""
        mock_client = MagicMock()
        mock_handle = MagicMock()
        mock_handle.cancel = AsyncMock(
            side_effect=RPCError(
                "connection refused", RPCStatusCode.UNAVAILABLE, b""
            )
        )
        mock_client.get_workflow_handle = MagicMock(return_value=mock_handle)

        self.patch(
            workflow_module,
            "get_client_async",
            AsyncMock(return_value=mock_client),
        )

        with self.assertRaises(RPCError) as cm:
            yield workflow_module.stop_workflow("deploy:test-id")

        self.assertIn("connection refused", str(cm.exception))
        mock_handle.cancel.assert_called_once()
