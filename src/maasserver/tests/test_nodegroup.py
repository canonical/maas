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

from maasserver.models import NodeGroup
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.worker_user import get_worker_user
from testtools.matchers import MatchesStructure


def make_dhcp_settings():
    """Create a dict of arbitrary nodegroup configuration parameters."""
    return {
        'subnet_mask': '255.0.0.0',
        'broadcast_ip': '10.255.255.255',
        'router_ip': factory.getRandomIPAddress(),
        'ip_range_low': '10.0.0.1',
        'ip_range_high': '10.254.254.254',
    }


class TestNodeGroupManager(TestCase):

    def test_new_creates_nodegroup(self):
        name = factory.make_name('nodegroup')
        ip = factory.getRandomIPAddress()
        self.assertThat(
            NodeGroup.objects.new(name, ip),
            MatchesStructure.fromExample({'name': name, 'worker_ip': ip}))

    def test_new_does_not_require_dhcp_settings(self):
        name = factory.make_name('nodegroup')
        ip = factory.getRandomIPAddress()
        nodegroup = NodeGroup.objects.new(name, ip)
        self.assertThat(
            nodegroup,
            MatchesStructure.fromExample({
                item: None
                for item in make_dhcp_settings().keys()}))

    def test_new_requires_all_dhcp_settings_or_none(self):
        name = factory.make_name('nodegroup')
        ip = factory.getRandomIPAddress()
        self.assertRaises(
            AssertionError,
            NodeGroup.objects.new, name, ip, subnet_mask='255.0.0.0')

    def test_new_creates_nodegroup_with_given_dhcp_settings(self):
        name = factory.make_name('nodegroup')
        ip = factory.getRandomIPAddress()
        dhcp_settings = make_dhcp_settings()
        nodegroup = NodeGroup.objects.new(name, ip, **dhcp_settings)
        nodegroup = reload_object(nodegroup)
        self.assertEqual(name, nodegroup.name)
        self.assertThat(
            nodegroup, MatchesStructure.fromExample(dhcp_settings))

    def test_new_assigns_token_and_key_for_worker_user(self):
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.getRandomIPAddress())
        self.assertIsNotNone(nodegroup.api_token)
        self.assertIsNotNone(nodegroup.api_key)
        self.assertEqual(get_worker_user(), nodegroup.api_token.user)
        self.assertEqual(nodegroup.api_key, nodegroup.api_token.key)

    def test_ensure_master_creates_minimal_master_nodegroup(self):
        self.assertThat(
            NodeGroup.objects.ensure_master(),
            MatchesStructure.fromExample({
                'name': 'master',
                'worker_ip': '127.0.0.1',
                'subnet_mask': None,
                'broadcast_ip': None,
                'router_ip': None,
                'ip_range_low': None,
                'ip_range_high': None,
            }))

    def test_writes_master_nodegroup_to_database(self):
        master = NodeGroup.objects.ensure_master()
        self.assertEqual(
            master.id, NodeGroup.objects.get(name=master.name).id)

    def test_ensure_master_returns_same_nodegroup_every_time(self):
        self.assertEqual(
            NodeGroup.objects.ensure_master().id,
            NodeGroup.objects.ensure_master().id)

    def test_ensure_master_preserves_existing_attributes(self):
        master = NodeGroup.objects.ensure_master()
        ip = factory.getRandomIPAddress()
        master.worker_ip = ip
        master.save()
        self.assertEqual(ip, NodeGroup.objects.ensure_master().worker_ip)
