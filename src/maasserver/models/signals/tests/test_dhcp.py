# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DHCP signals."""

__all__ = []

import random

from django.conf import settings
from maasserver import dhcp
from maasserver.enum import (
    NODEGROUP_STATUS,
    NODEGROUPINTERFACE_MANAGEMENT,
)
from maasserver.models import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from mock import (
    ANY,
    call,
)
from netaddr import IPAddress


class TestDHCPSignals(MAASServerTestCase):
    """Tests for DHCP signals triggered when saving a cluster interface."""

    def setUp(self):
        super(TestDHCPSignals, self).setUp()
        self.patch_autospec(dhcp, "configure_dhcp")

    def test_dhcp_config_gets_written_when_nodegroup_becomes_active(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.DISABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)

        nodegroup.accept()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_nodegroup_name_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)

        nodegroup.name = factory.make_name('domain')
        nodegroup.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_interface_IP_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.nodegroupinterface_set.all()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.ip = factory.pick_ip_in_network(
            interface.network, but_not=[interface.ip])
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_interface_management_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.UNMANAGED)
        [interface] = nodegroup.nodegroupinterface_set.all()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.management = NODEGROUPINTERFACE_MANAGEMENT.DHCP
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_interface_name_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.interface = factory.make_name('itf')
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_netmask_changes(self):
        network = factory.make_ipv4_network(slash='255.255.255.0')
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED, network=network,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.subnet_mask = "255.255.0.0"
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_interface_router_ip_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.subnet.gateway_ip = factory.pick_ip_in_network(
            interface.network, but_not=[interface.subnet.gateway_ip])
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_gets_written_when_ip_range_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.ip_range_low = str(
            IPAddress(interface.ip_range_low) + 1)
        interface.ip_range_high = str(
            IPAddress(interface.ip_range_high) - 1)
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockCalledOnceWith(nodegroup))

    def test_dhcp_config_is_not_written_when_foreign_dhcp_changes(self):
        nodegroup = factory.make_NodeGroup(
            status=NODEGROUP_STATUS.ENABLED,
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        [interface] = nodegroup.get_managed_interfaces()
        self.patch(settings, "DHCP_CONNECT", True)

        interface.foreign_dhcp = factory.pick_ip_in_network(interface.network)
        interface.save()

        self.assertThat(dhcp.configure_dhcp, MockNotCalled())

    def test_dhcp_config_gets_written_when_ntp_server_changes(self):
        # When the "ntp_server" Config item is changed, check that all
        # nodegroups get their DHCP config re-written.
        num_active_nodegroups = random.randint(1, 10)
        num_inactive_nodegroups = random.randint(1, 10)
        for _ in range(num_active_nodegroups):
            factory.make_NodeGroup(
                status=NODEGROUP_STATUS.ENABLED,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        for _ in range(num_inactive_nodegroups):
            factory.make_NodeGroup(
                status=NODEGROUP_STATUS.DISABLED,
                management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)

        Config.objects.set_config("ntp_server", factory.make_ipv4_address())

        # Every nodegroup is updated, including those that are DISABLED.
        expected_call_one_nodegroup = [call(ANY)]
        expected_calls = expected_call_one_nodegroup * (
            num_active_nodegroups + num_inactive_nodegroups)
        self.assertThat(dhcp.configure_dhcp, MockCallsMatch(*expected_calls))

    def test_dhcp_config_gets_written_when_managed_interface_is_deleted(self):
        interface = factory.make_NodeGroupInterface(
            factory.make_NodeGroup(status=NODEGROUP_STATUS.ENABLED),
            management=NODEGROUPINTERFACE_MANAGEMENT.DHCP)
        self.patch(settings, "DHCP_CONNECT", True)

        interface.delete()

        self.assertThat(
            dhcp.configure_dhcp, MockCalledOnceWith(interface.nodegroup))
