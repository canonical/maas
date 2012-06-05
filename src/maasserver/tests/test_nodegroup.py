# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the NodeGroup model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from testtools.matchers import MatchesStructure


class TestNodeGroup(TestCase):

    def test_model_stores_to_database(self):
        ng = factory.make_node_group(
            name=factory.getRandomString(80),
            worker_ip="10.1.1.1",
            subnet_mask="255.0.0.0",
            broadcast_ip="10.255.255.255",
            router_ip="10.1.1.254",
            ip_range_low="10.1.1.2",
            ip_range_high="10.254.254.253")
        self.assertThat(
            ng, MatchesStructure.byEquality(
                worker_ip="10.1.1.1",
                subnet_mask="255.0.0.0",
                broadcast_ip="10.255.255.255",
                router_ip="10.1.1.254",
                ip_range_low="10.1.1.2",
                ip_range_high="10.254.254.253"))
