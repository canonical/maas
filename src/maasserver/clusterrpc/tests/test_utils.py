# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:mod:`maasserver.clusterrpc.utils`."""

__all__ = []

import random

from maasserver.clusterrpc import utils
from maasserver.node_action import RPC_EXCEPTIONS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import async
from maastesting.matchers import MockCalledOnceWith
from mock import sentinel
from provisioningserver.rpc.exceptions import NoConnectionsAvailable


class TestCallClusters(MAASServerTestCase):
    """Tests for `utils.call_clusters`."""

    def test__gets_clients(self):
        rack = factory.make_RackController()
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None
        async_gather = self.patch(async, "gather")
        async_gather.return_value = []

        # call_clusters returns with nothing because we patched out
        # async.gather, but we're interested in the side-effect: getClientFor
        # has been called for the accepted nodegroup.
        self.assertItemsEqual([], utils.call_clusters(sentinel.command))
        self.assertThat(getClientFor, MockCalledOnceWith(rack.system_id))


class TestGetErrorMessageForException(MAASServerTestCase):

    def test_returns_message_if_exception_has_one(self):
        error_message = factory.make_name("exception")
        self.assertEqual(
            error_message,
            utils.get_error_message_for_exception(Exception(error_message)))

    def test_returns_message_if_exception_has_none(self):
        exception_class = random.choice(RPC_EXCEPTIONS)
        error_message = (
            "Unexpected exception: %s. See "
            "/var/log/maas/regiond.log "
            "on the region server for more information." %
            exception_class.__name__)
        self.assertEqual(
            error_message,
            utils.get_error_message_for_exception(exception_class()))

    def test_returns_cluster_name_in_no_connections_error_message(self):
        rack = factory.make_RackController()
        exception = NoConnectionsAvailable(
            "Unable to connect!", uuid=rack.system_id)
        self.assertEqual(
            "Unable to connect to rack controller '%s' (%s); no connections "
            "available." % (rack.hostname, rack.system_id),
            utils.get_error_message_for_exception(exception))
