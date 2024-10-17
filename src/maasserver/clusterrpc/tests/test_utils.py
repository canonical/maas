# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:mod:`maasserver.clusterrpc.utils`."""


import random
from unittest.mock import Mock, sentinel

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from fixtures import FakeLogger
from twisted.python.failure import Failure

from maasserver.clusterrpc import utils
from maasserver.clusterrpc.utils import call_racks_synchronously
from maasserver.node_action import RPC_EXCEPTIONS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import asynchronous
from provisioningserver.rpc.exceptions import NoConnectionsAvailable


class MockFailure(Failure):
    """Fake twisted Failure object.

    Purposely doesn't call super().__init__().
    """

    def __init__(self):
        self.type = type(self)
        self.frames = []
        self.value = "Mock failure"


class TestCallClusters(MAASServerTestCase):
    """Tests for `utils.call_clusters`."""

    def test_gets_clients(self):
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None
        async_gather = self.patch(asynchronous, "gatherCallResults")
        async_gather.return_value = []

        # call_clusters returns with nothing because we patched out
        # asynchronous.gather, but we're interested in the side-effect:
        # getClientFor has been called for the accepted nodegroup.
        self.assertEqual([], list(utils.call_clusters(sentinel.command)))
        getClientFor.assert_called_once_with(rack.system_id)

    def test_with_successful_callbacks(self):
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None
        partial = self.patch(utils, "partial")
        partial.return_value = sentinel.partial
        async_gather = self.patch(asynchronous, "gatherCallResults")
        async_gather.return_value = (
            result for result in [(sentinel.partial, sentinel.result)]
        )
        available_callback = Mock()
        unavailable_callback = Mock()
        success_callback = Mock()
        failed_callback = Mock()
        timeout_callback = Mock()
        result = list(
            utils.call_clusters(
                sentinel.command,
                available_callback=available_callback,
                unavailable_callback=unavailable_callback,
                success_callback=success_callback,
                failed_callback=failed_callback,
                timeout_callback=timeout_callback,
            )
        )
        self.assertEqual([sentinel.result], result)
        available_callback.assert_called_once_with(rack)
        unavailable_callback.assert_not_called()
        success_callback.assert_called_once_with(rack)
        failed_callback.assert_not_called()
        timeout_callback.assert_not_called()

    def test_with_unavailable_callbacks(self):
        logger = self.useFixture(FakeLogger("maasserver"))
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.side_effect = NoConnectionsAvailable
        partial = self.patch(utils, "partial")
        partial.return_value = sentinel.partial
        async_gather = self.patch(asynchronous, "gatherCallResults")
        async_gather.return_value = iter([])
        available_callback = Mock()
        unavailable_callback = Mock()
        success_callback = Mock()
        failed_callback = Mock()
        timeout_callback = Mock()
        result = list(
            utils.call_clusters(
                sentinel.command,
                available_callback=available_callback,
                unavailable_callback=unavailable_callback,
                success_callback=success_callback,
                failed_callback=failed_callback,
                timeout_callback=timeout_callback,
            )
        )
        self.assertEqual([], result)
        available_callback.assert_not_called()
        unavailable_callback.assert_called_once_with(rack)
        success_callback.assert_not_called()
        failed_callback.assert_not_called()
        timeout_callback.assert_not_called()
        self.assertIn("Unable to get RPC connection", logger.output)

    def test_with_failed_callbacks(self):
        logger = self.useFixture(FakeLogger("maasserver"))
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None
        partial = self.patch(utils, "partial")
        partial.return_value = sentinel.partial
        async_gather = self.patch(asynchronous, "gatherCallResults")
        async_gather.return_value = (
            result for result in [(sentinel.partial, MockFailure())]
        )
        available_callback = Mock()
        unavailable_callback = Mock()
        success_callback = Mock()
        failed_callback = Mock()
        timeout_callback = Mock()
        result = list(
            utils.call_clusters(
                sentinel.command,
                available_callback=available_callback,
                unavailable_callback=unavailable_callback,
                success_callback=success_callback,
                failed_callback=failed_callback,
                timeout_callback=timeout_callback,
            )
        )
        self.assertEqual([], result)
        available_callback.assert_called_once_with(rack)
        unavailable_callback.assert_not_called()
        success_callback.assert_not_called()
        failed_callback.assert_called_once_with(rack)
        timeout_callback.assert_not_called()

        self.assertRegex(
            logger.output,
            "Exception during .* on rack controller.*MockFailure: ",
        )

    def test_with_timeout_callbacks(self):
        logger = self.useFixture(FakeLogger("maasserver"))
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None
        partial = self.patch(utils, "partial")
        partial.return_value = sentinel.partial
        async_gather = self.patch(asynchronous, "gatherCallResults")
        async_gather.return_value = (result for result in [])
        available_callback = Mock()
        unavailable_callback = Mock()
        success_callback = Mock()
        failed_callback = Mock()
        timeout_callback = Mock()
        result = list(
            utils.call_clusters(
                sentinel.command,
                available_callback=available_callback,
                unavailable_callback=unavailable_callback,
                success_callback=success_callback,
                failed_callback=failed_callback,
                timeout_callback=timeout_callback,
            )
        )
        self.assertEqual([], result)
        available_callback.assert_called_once_with(rack)
        unavailable_callback.assert_not_called()
        success_callback.assert_not_called()
        failed_callback.assert_not_called()
        timeout_callback.assert_called_once_with(rack)

        self.assertIn("RPC connection timed out", logger.output)


class TestCallRacksSynchronously(MAASServerTestCase):
    """Tests for `utils.call_rakcks_synchronously`."""

    def test_gets_clients(self):
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None
        async_gather = self.patch(asynchronous, "gatherCallResults")
        async_gather.return_value = []

        # call_clusters returns with nothing because we patched out
        # asynchronous.gather, but we're interested in the side-effect:
        # getClientFor has been called for the accepted nodegroup.
        self.assertEqual(
            [], list(call_racks_synchronously(sentinel.command).results)
        )
        getClientFor.assert_called_once_with(rack.system_id)


class TestGetErrorMessageForException(MAASServerTestCase):
    def test_returns_message_if_exception_has_one(self):
        error_message = factory.make_name("exception")
        self.assertEqual(
            error_message,
            utils.get_error_message_for_exception(Exception(error_message)),
        )

    def test_returns_message_if_exception_has_none(self):
        exception_class = random.choice(RPC_EXCEPTIONS)
        error_message = (
            "Unexpected exception: %s. See "
            "/var/log/maas/regiond.log "
            "on the region server for more information."
            % exception_class.__name__
        )
        self.assertEqual(
            error_message,
            utils.get_error_message_for_exception(exception_class()),
        )

    def test_returns_cluster_name_in_no_connections_error_message(self):
        rack = factory.make_RackController()
        exception = NoConnectionsAvailable(
            "Unable to connect!", uuid=rack.system_id
        )
        self.assertEqual(
            "Unable to connect to rack controller '%s' (%s); no connections "
            "available." % (rack.hostname, rack.system_id),
            utils.get_error_message_for_exception(exception),
        )

    def test_ValidationError(self):
        exception = ValidationError({NON_FIELD_ERRORS: "Some error"})
        self.assertEqual(
            utils.get_error_message_for_exception(exception), "Some error"
        )
