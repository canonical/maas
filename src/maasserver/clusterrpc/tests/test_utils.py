# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:mod:`maasserver.clusterrpc.utils`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.clusterrpc import utils
from maasserver.enum import NODEGROUP_STATUS
from maasserver.node_action import RPC_EXCEPTIONS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import async
from maastesting.matchers import MockCalledOnceWith
from mock import sentinel
from provisioningserver.rpc.exceptions import (
    MultipleFailures,
    NoConnectionsAvailable,
    )
from twisted.python.failure import Failure


class TestCallClusters(MAASServerTestCase):
    """Tests for `utils.call_clusters`."""

    def test__gets_clients_for_accepted_nodegroups_only(self):
        # Create several pending nodegroups.
        nodegroups = [
            factory.make_NodeGroup(
                status=NODEGROUP_STATUS.PENDING)
            for _ in xrange(5)
        ]

        # Accept one of them at random.
        accepted = random.choice(nodegroups)
        accepted.accept()

        # Watch those clients that are requested.
        getClientFor = self.patch(utils, "getClientFor")
        getClientFor.return_value = lambda: None

        # Prevent any calls from being made.
        async_gather = self.patch(async, "gather")
        async_gather.return_value = []

        # call_clusters returns with nothing because we patched out
        # async.gather, but we're interested in the side-effect: getClientFor
        # has been called for the accepted nodegroup.
        self.assertItemsEqual([], utils.call_clusters(sentinel.command))
        self.assertThat(getClientFor, MockCalledOnceWith(accepted.uuid))


class TestGetErrorMessageForException(MAASServerTestCase):

    def test_returns_message_if_exception_has_one(self):
        error_message = factory.make_name("exception")
        self.assertEqual(
            error_message,
            utils.get_error_message_for_exception(Exception(error_message)))

    def test_returns_message_if_exception_has_none(self):
        # MultipleFailures is handled differently, so exclude it from
        # the possible exceptions.
        exception_class = random.choice(
            [cls for cls in RPC_EXCEPTIONS if cls is not MultipleFailures])
        error_message = (
            "Unexpected exception: %s. See "
            "/var/log/maas/maas-django.log "
            "on the region server for more information." %
            exception_class.__name__)
        self.assertEqual(
            error_message,
            utils.get_error_message_for_exception(exception_class()))

    def test_returns_single_message_for_multiple_failures(self):
        failures = MultipleFailures(
            *(Failure(cls()) for cls in RPC_EXCEPTIONS
                if cls is not MultipleFailures))
        error_message = (
            "Multiple failures encountered. See /var/log/maas/maas-django.log"
            " on the region server for more information.")
        self.assertEqual(
            error_message, utils.get_error_message_for_exception(failures))

    def test_returns_cluster_name_in_no_connections_error_message(self):
        cluster = factory.make_NodeGroup()
        exception = NoConnectionsAvailable(
            "Unable to connect!", uuid=cluster.uuid)
        self.assertEqual(
            "Unable to connect to cluster '%s' (%s); no connections "
            "available." % (cluster.cluster_name, cluster.uuid),
            utils.get_error_message_for_exception(exception))
