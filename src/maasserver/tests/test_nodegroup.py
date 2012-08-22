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

from maasserver.models import (
    Config,
    NodeGroup,
    )
from maasserver.testing import reload_object
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.worker_user import get_worker_user
from maastesting.celery import CeleryFixture
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import ContainsAll
from provisioningserver import tasks
from provisioningserver.omshell import (
    generate_omapi_key,
    Omshell,
    )
from testresources import FixtureResource
from testtools.matchers import (
    FileContains,
    GreaterThan,
    MatchesStructure,
    )


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

    def test_new_creates_nodegroup_with_empty_dhcp_key(self):
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.getRandomIPAddress())
        self.assertEqual('', nodegroup.dhcp_key)

    def test_new_stores_dhcp_key_on_nodegroup(self):
        key = generate_omapi_key()
        nodegroup = NodeGroup.objects.new(
            factory.make_name('nodegroup'), factory.getRandomIPAddress(),
            dhcp_key=key)
        self.assertEqual(key, nodegroup.dhcp_key)

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

    def test_ensure_master_writes_master_nodegroup_to_database(self):
        master = NodeGroup.objects.ensure_master()
        self.assertEqual(
            master.id, NodeGroup.objects.get(name=master.name).id)

    def test_ensure_master_creates_dhcp_key(self):
        master = NodeGroup.objects.ensure_master()
        self.assertThat(len(master.dhcp_key), GreaterThan(20))

    def test_ensure_master_returns_same_nodegroup_every_time(self):
        self.assertEqual(
            NodeGroup.objects.ensure_master().id,
            NodeGroup.objects.ensure_master().id)

    def test_ensure_master_does_not_return_other_nodegroup(self):
        self.assertNotEqual(
            NodeGroup.objects.new(
                factory.make_name('nodegroup'), factory.getRandomIPAddress()),
            NodeGroup.objects.ensure_master())

    def test_ensure_master_preserves_existing_attributes(self):
        master = NodeGroup.objects.ensure_master()
        ip = factory.getRandomIPAddress()
        master.worker_ip = ip
        master.save()
        self.assertEqual(ip, NodeGroup.objects.ensure_master().worker_ip)

    def test_get_by_natural_key_looks_up_by_name(self):
        nodegroup = factory.make_node_group()
        self.assertEqual(
            nodegroup, NodeGroup.objects.get_by_natural_key(nodegroup.name))

    def test_get_by_natural_key_will_not_return_other_nodegroup(self):
        factory.make_node_group()
        self.assertRaises(
            NodeGroup.DoesNotExist,
            NodeGroup.objects.get_by_natural_key,
            factory.make_name("nonexistent-nodegroup"))


class TestNodeGroup(TestCase):

    resources = (
        ('celery', FixtureResource(CeleryFixture())),
        )

    def test_is_dhcp_enabled_returns_True_if_fully_set_up(self):
        Config.objects.set_config('manage_dhcp', True)
        self.assertTrue(factory.make_node_group().is_dhcp_enabled())

    def test_is_dhcp_enabled_returns_False_if_disabled(self):
        Config.objects.set_config('manage_dhcp', False)
        self.assertFalse(factory.make_node_group().is_dhcp_enabled())

    def test_is_dhcp_enabled_returns_False_if_config_is_missing(self):
        Config.objects.set_config('manage_dhcp', True)
        required_fields = [
            'subnet_mask', 'broadcast_ip', 'ip_range_low', 'ip_range_high']
        # Map each required field's name to a nodegroup that has just
        # that field set to None.
        nodegroups = {
            field: factory.make_node_group()
            for field in required_fields}
        for field, nodegroup in nodegroups.items():
            setattr(nodegroup, field, None)
            nodegroup.save()
        # List any nodegroups from this mapping that have DHCP
        # management enabled.  There should not be any.
        self.assertEqual([], [
            field
            for field, nodegroup in nodegroups.items()
                if nodegroup.is_dhcp_enabled()])

    def test_set_up_dhcp_writes_dhcp_config(self):
        conf_file = self.make_file(contents=factory.getRandomString())
        self.patch(tasks, 'DHCP_CONFIG_FILE', conf_file)
        # Silence dhcpd restart.
        self.patch(tasks, 'check_call', FakeMethod())
        nodegroup = factory.make_node_group(
            dhcp_key=factory.getRandomString())
        nodegroup.set_up_dhcp()
        dhcp_params = [
            'dhcp_key', 'subnet_mask', 'broadcast_ip', 'router_ip',
            'ip_range_low', 'ip_range_high']
        expected = [getattr(nodegroup, param) for param in dhcp_params]
        self.assertThat(
            conf_file,
            FileContains(
                matcher=ContainsAll(expected)))

    def test_set_up_dhcp_reloads_dhcp_server(self):
        self.patch(tasks, 'DHCP_CONFIG_FILE', self.make_file())
        recorder = FakeMethod()
        self.patch(tasks, 'check_call', recorder)
        nodegroup = factory.make_node_group()
        nodegroup.set_up_dhcp()
        self.assertEqual(1, recorder.call_count)

    def test_add_dhcp_host_maps_adds_maps_if_managing_dhcp(self):
        self.patch(Omshell, 'create', FakeMethod())
        nodegroup = factory.make_node_group()
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        self.assertEqual(
            [(leases.keys()[0], leases.values()[0])],
            Omshell.create.extract_args())

    def test_add_dhcp_host_maps_does_nothing_if_not_managing_dhcp(self):
        self.patch(Omshell, 'create', FakeMethod())
        nodegroup = factory.make_node_group()
        self.patch(nodegroup, 'is_dhcp_enabled', FakeMethod(result=False))
        leases = factory.make_random_leases()
        nodegroup.add_dhcp_host_maps(leases)
        self.assertEqual([], Omshell.create.extract_args())
