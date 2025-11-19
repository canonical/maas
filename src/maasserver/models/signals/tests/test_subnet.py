# Copyright 2019-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of subnet signals."""

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import IPADDRESS_TYPE, RDNS_MODE
from maasserver.models import DNSPublication
import maasserver.models.signals.subnet as subnet_signals_module
import maasserver.models.signals.vlan as vlan_signals_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import post_commit_hooks


class TestSubnetSignals(MAASServerTestCase):
    scenarios = (
        ("ipv4", {"network_maker": factory.make_ipv4_network}),
        ("ipv6", {"network_maker": factory.make_ipv6_network}),
    )

    def test_creating_subnet_links_to_existing_ip_address(self):
        network = self.network_maker()
        ip = factory.pick_ip_in_network(network)
        ip_address = factory.make_StaticIPAddress(
            ip=ip, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )

        # Ensure that for this test to really be testing the logic the
        # `StaticIPAddress` needs to not have a subnet assigned.
        self.assertIsNone(ip_address.subnet)

        # Creating the subnet, must link the created `StaticIPAddress` to
        # that subnet.
        subnet = factory.make_Subnet(cidr=network.cidr)
        ip_address.refresh_from_db()
        self.assertEqual(subnet, ip_address.subnet)

    def test_updating_subnet_removes_existing_ip_address_adds_another(self):
        network1 = self.network_maker()
        network2 = self.network_maker(but_not=[network1])
        ip1 = factory.pick_ip_in_network(network1)
        ip2 = factory.pick_ip_in_network(network2)

        # Create the second IP address not linked to network2.
        ip_address2 = factory.make_StaticIPAddress(
            ip=ip2, alloc_type=IPADDRESS_TYPE.USER_RESERVED
        )
        self.assertIsNone(ip_address2.subnet)

        # Create the first IP address assigned to the network.
        subnet = factory.make_Subnet(cidr=network1.cidr)
        ip_address1 = factory.make_StaticIPAddress(
            ip=ip1, alloc_type=IPADDRESS_TYPE.USER_RESERVED, subnet=subnet
        )
        self.assertEqual(subnet, ip_address1.subnet)

        # Update the subnet to have the CIDR of network2.
        subnet.cidr = network2.cidr
        subnet.gateway_ip = None
        subnet.save()

        # IP1 should not have a subnet, and IP2 should not have the subnet.
        ip_address1.refresh_from_db()
        ip_address2.refresh_from_db()
        self.assertIsNone(ip_address1.subnet)
        self.assertEqual(subnet, ip_address2.subnet)


class TestPostSaveSubnetSignal(MAASServerTestCase):
    def test_save_subnet_with_rdns_creates_dnspublication(self):
        factory.make_Subnet(cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DEFAULT)
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual("added subnet 10.0.0.0/24", dnspublication.source)

    def test_save_subnet_with_rdns_disabled_does_not_create_dnspublication(
        self,
    ):
        factory.make_Subnet(cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DISABLED)
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(1, dnspublication.serial)

    def test_save_subnet_starts_dhcp_workflow_if_dhcp_on(
        self,
    ):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            factory.make_Subnet(
                cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DISABLED, vlan=vlan
            )

        subnet_start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_save_subnet_starts_dhcp_workflow_if_dhcp_relay(
        self,
    ):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            relay_vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            vlan = factory.make_VLAN(relay_vlan=relay_vlan)
            factory.make_Subnet(
                cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DISABLED, vlan=vlan
            )

        subnet_start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id]),
            task_queue="region",
        )


class TestPostDeleteSubnetSignal(MAASServerTestCase):
    def test_delete_subnet_with_rdns_creates_dnspublication(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DEFAULT
        )
        subnet.delete()
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual("removed subnet 10.0.0.0/24", dnspublication.source)

    def test_delete_subnet_with_rdns_disabled_does_not_create_dnspublication(
        self,
    ):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DISABLED
        )
        dnspublication_count_before_delete = DNSPublication.objects.count()
        subnet.delete()
        self.assertEqual(
            dnspublication_count_before_delete, DNSPublication.objects.count()
        )

    def test_delete_subnet_starts_dhcp_workflow_if_dhcp_on(
        self,
    ):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            subnet = factory.make_Subnet(
                cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DISABLED, vlan=vlan
            )
            subnet_start_workflow_mock.reset_mock()
            subnet.delete()

        subnet_start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id]),
            task_queue="region",
        )

    def test_delete_subnet_starts_dhcp_workflow_if_dhcp_relay(
        self,
    ):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            relay_vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            vlan = factory.make_VLAN(relay_vlan=relay_vlan)
            subnet = factory.make_Subnet(
                cidr="10.0.0.0/24", rdns_mode=RDNS_MODE.DISABLED, vlan=vlan
            )
            subnet_start_workflow_mock.reset_mock()
            subnet.delete()

        subnet_start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id]),
            task_queue="region",
        )


class TestUpdateSubnetSignal(MAASServerTestCase):
    def test_update_subnet_creates_dnspublication(self):
        subnet = factory.make_Subnet(
            cidr="10.0.0.0/24",
            gateway_ip="10.0.0.1",
            rdns_mode=RDNS_MODE.DEFAULT,
        )
        subnet.cidr = "20.0.0.0/24"
        subnet.gateway_ip = "20.0.0.254"
        subnet.rdns_mode = RDNS_MODE.DISABLED
        subnet.allow_dns = False
        subnet.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertIn("cidr changed", dnspublication.source)
        self.assertIn("rdns changed", dnspublication.source)
        self.assertIn("allow_dns changed", dnspublication.source)


class TestSubnetDHCPSignal(MAASServerTestCase):
    def test_save_calls_configure_dhcp_workflow_when_dhcp_on(self):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            new_vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            subnet = factory.make_Subnet(vlan=vlan)
            subnet_start_workflow_mock.reset_mock()
            subnet.vlan = new_vlan
            subnet.save()

        subnet_start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id, new_vlan.id]),
            task_queue="region",
        )

    def test_save_calls_configure_dhcp_workflow_when_dhcp_relay(self):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            rack_controller = factory.make_RackController()
            relay_vlan = factory.make_VLAN(
                dhcp_on=True, primary_rack=rack_controller
            )
            vlan = factory.make_VLAN(relay_vlan=relay_vlan)
            new_vlan = factory.make_VLAN(relay_vlan=relay_vlan)
            subnet = factory.make_Subnet(vlan=vlan)
            subnet_start_workflow_mock.reset_mock()
            subnet.vlan = new_vlan
            subnet.save()

        subnet_start_workflow_mock.assert_called_once_with(
            workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
            param=ConfigureDHCPParam(vlan_ids=[vlan.id, new_vlan.id]),
            task_queue="region",
        )

    def test_save_does_not_configure_dhcp_workflow_when_dhcp_off(self):
        self.patch(vlan_signals_module, "start_workflow")
        subnet_start_workflow_mock = self.patch(
            subnet_signals_module, "start_workflow"
        )

        with post_commit_hooks:
            vlan = factory.make_VLAN(dhcp_on=False)
            new_vlan = factory.make_VLAN(dhcp_on=False)
            subnet = factory.make_Subnet(vlan=vlan)
            subnet_start_workflow_mock.reset_mock()

        subnet.vlan = new_vlan
        subnet.save()
        subnet_start_workflow_mock.assert_not_called()
