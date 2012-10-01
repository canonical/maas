# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the config_master_dhcp command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from optparse import OptionValueError

from django.conf import settings
from django.core.management import call_command
from maasserver import dhcp
from maasserver.enum import NODEGROUPINTERFACE_MANAGEMENT
from maasserver.management.commands.config_master_dhcp import name_option
from maasserver.models import NodeGroup
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from testtools.matchers import MatchesStructure


def make_master_constants():
    """Return the standard, unchanging config for the master nodegroup."""
    return {
        'name': 'master',
    }


def make_dhcp_settings():
    """Return an arbitrary dict of DHCP settings."""
    network = factory.getRandomNetwork()
    return {
        'ip': factory.getRandomIPInNetwork(network),
        'interface': factory.make_name('interface'),
        'subnet_mask': str(network.netmask),
        'broadcast_ip': str(network.broadcast),
        'router_ip': factory.getRandomIPInNetwork(network),
        'ip_range_low': factory.getRandomIPInNetwork(network),
        'ip_range_high': factory.getRandomIPInNetwork(network),
    }


def make_cleared_dhcp_settings():
    """Return dict of cleared DHCP settings."""
    return dict.fromkeys(make_dhcp_settings())


class TestConfigMasterDHCP(TestCase):

    def setUp(self):
        super(TestConfigMasterDHCP, self).setUp()
        # Make sure any attempts to write a dhcp config do nothing.
        self.patch(dhcp, 'configure_dhcp')
        self.patch(settings, 'DHCP_CONNECT', True)

    def test_configures_dhcp_for_master_nodegroup(self):
        settings = make_dhcp_settings()
        call_command('config_master_dhcp', **settings)
        master = NodeGroup.objects.get(name='master')
        interface = master.get_managed_interface()
        self.assertThat(
            master,
            MatchesStructure.byEquality(**make_master_constants()))
        self.assertThat(
            interface, MatchesStructure.byEquality(
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP, **settings))

    def test_configures_dhcp_for_master_nodegroup_existing_master(self):
        management = NODEGROUPINTERFACE_MANAGEMENT.DHCP_AND_DNS
        master = factory.make_node_group(uuid='master', management=management)
        settings = make_dhcp_settings()
        call_command('config_master_dhcp', **settings)
        master = NodeGroup.objects.ensure_master()
        interface = master.get_managed_interface()
        self.assertThat(
            interface, MatchesStructure.byEquality(
                management=interface.management, **settings))

    def test_clears_dhcp_settings(self):
        master = NodeGroup.objects.ensure_master()
        for attribute, value in make_dhcp_settings().items():
            setattr(master, attribute, value)
        master.save()
        call_command('config_master_dhcp', clear=True)
        self.assertThat(
            master,
            MatchesStructure.byEquality(**make_master_constants()))
        self.assertIsNone(master.get_managed_interface())

    def test_does_not_accept_partial_dhcp_settings(self):
        settings = make_dhcp_settings()
        del settings['subnet_mask']
        self.assertRaises(
            OptionValueError,
            call_command, 'config_master_dhcp', **settings)

    def test_ignores_nonsense_settings_when_clear_is_passed(self):
        settings = make_dhcp_settings()
        call_command('config_master_dhcp', **settings)
        settings['subnet_mask'] = '@%$^&'
        settings['broadcast_ip'] = ''
        call_command('config_master_dhcp', clear=True, **settings)
        master = NodeGroup.objects.get(name='master')
        self.assertIsNone(master.get_managed_interface())

    def test_clear_conflicts_with_ensure(self):
        self.assertRaises(
            OptionValueError,
            call_command, 'config_master_dhcp', clear=True, ensure=True)

    def test_ensure_creates_master_nodegroup_without_dhcp_settings(self):
        call_command('config_master_dhcp', ensure=True)
        self.assertIsNone(
            NodeGroup.objects.get(name='master').get_managed_interface())

    def test_ensure_leaves_cleared_settings_cleared(self):
        call_command('config_master_dhcp', clear=True)
        call_command('config_master_dhcp', ensure=True)
        master = NodeGroup.objects.get(name='master')
        self.assertIsNone(master.get_managed_interface())

    def test_ensure_leaves_dhcp_settings_intact(self):
        settings = make_dhcp_settings()
        call_command('config_master_dhcp', **settings)
        call_command('config_master_dhcp', ensure=True)
        self.assertThat(
            NodeGroup.objects.get(name='master').get_managed_interface(),
            MatchesStructure.byEquality(**settings))

    def test_name_option_turns_dhcp_setting_name_into_option(self):
        self.assertEqual('--subnet-mask', name_option('subnet_mask'))

    def test_configures_dhcp(self):
        NodeGroup.objects.ensure_master()
        self.patch(dhcp, 'configure_dhcp')
        settings = make_dhcp_settings()
        call_command('config_master_dhcp', **settings)
        self.assertEqual(1, dhcp.configure_dhcp.call_count)
