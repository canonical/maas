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
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import async
from maastesting.matchers import MockCalledOnceWith
from mock import sentinel


class TestCallClusters(MAASServerTestCase):
    """Tests for `utils.call_clusters`."""

    def test__gets_clients_for_accepted_nodegroups_only(self):
        # Create several pending nodegroups.
        nodegroups = [
            factory.make_node_group(
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
