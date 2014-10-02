# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :py:module:`~maasserver.rpc.cluster`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.enum import NODEGROUP_STATUS_CHOICES
from maasserver.rpc.clusters import get_cluster_status
from maasserver.testing.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc.exceptions import NoSuchCluster


class TestGetClusterStatus(MAASTestCase):

    def test_returns_empty_list_when_cluster_does_not_exist(self):
        uuid = factory.make_UUID()
        self.assertRaises(NoSuchCluster, get_cluster_status, uuid)

    def test_returns_cluster_status(self):
        status = factory.pick_choice(NODEGROUP_STATUS_CHOICES)
        nodegroup = factory.make_NodeGroup(status=status)
        self.assertEqual(
            {b"status": status},
            get_cluster_status(nodegroup.uuid))
