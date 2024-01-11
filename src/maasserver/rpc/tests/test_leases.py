# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `rpc.leases`."""


from datetime import datetime
import random
import time

from django.utils import timezone
from netaddr import IPAddress

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_FAMILY, IPADDRESS_TYPE
from maasserver.fields import normalise_macaddress
from maasserver.models import DNSResource
from maasserver.models.interface import UnknownInterface
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.rpc.leases import LeaseUpdateError, update_lease
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import get_one, reload_object


class TestUpdateLease(MAASServerTestCase):
    def make_kwargs(
        self,
        action=None,
        mac=None,
        ip=None,
        timestamp=None,
        lease_time=None,
        hostname=None,
        subnet=None,
    ):
        if action is None:
            action = random.choice(["commit", "expiry", "release"])
        if mac is None:
            mac = factory.make_mac_address()
        if ip is None:
            if subnet is not None:
                ip = factory.pick_ip_in_network(subnet.get_ipnetwork())
            else:
                ip = factory.make_ip_address()
        if timestamp is None:
            timestamp = int(time.time())
        if action == "commit":
            if lease_time is None:
                lease_time = random.randint(30, 1000)
            if hostname is None:
                hostname = factory.make_name("host")
        ip_family = "ipv4"
        if IPAddress(ip).version == IPADDRESS_FAMILY.IPv6:
            ip_family = "ipv6"
        return {
            "action": action,
            "mac": mac,
            "ip": ip,
            "ip_family": ip_family,
            "timestamp": timestamp,
            "lease_time": lease_time,
            "hostname": hostname,
        }

    def make_managed_subnet(self):
        return factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )

    def test_raises_LeaseUpdateError_for_unknown_action(self):
        action = factory.make_name("action")
        kwargs = self.make_kwargs(action=action)
        error = self.assertRaises(LeaseUpdateError, update_lease, **kwargs)
        self.assertEqual("Unknown lease action: %s" % action, str(error))

    def test_raises_LeaseUpdateError_for_no_subnet(self):
        kwargs = self.make_kwargs()
        error = self.assertRaises(LeaseUpdateError, update_lease, **kwargs)
        self.assertEqual("No subnet exists for: %s" % kwargs["ip"], str(error))

    def test_raises_LeaseUpdateError_for_ipv4_mismatch(self):
        ipv6_network = factory.make_ipv6_network()
        subnet = factory.make_Subnet(cidr=str(ipv6_network.cidr))
        kwargs = self.make_kwargs(subnet=subnet)
        kwargs["ip_family"] = "ipv4"
        error = self.assertRaises(LeaseUpdateError, update_lease, **kwargs)
        self.assertEqual(
            "Family for the subnet does not match. Expected: ipv4", str(error)
        )

    def test_raises_LeaseUpdateError_for_ipv6_mismatch(self):
        ipv4_network = factory.make_ipv4_network()
        subnet = factory.make_Subnet(cidr=str(ipv4_network.cidr))
        kwargs = self.make_kwargs(subnet=subnet)
        kwargs["ip_family"] = "ipv6"
        error = self.assertRaises(LeaseUpdateError, update_lease, **kwargs)
        self.assertEqual(
            "Family for the subnet does not match. Expected: ipv6", str(error)
        )

    def test_does_nothing_if_expiry_for_unknown_mac(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(action="expiry", ip=ip)
        update_lease(**kwargs)
        self.assertIsNone(
            StaticIPAddress.objects.filter(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip
            ).first()
        )

    def test_does_nothing_if_release_for_unknown_mac(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(action="release", ip=ip)
        update_lease(**kwargs)
        self.assertIsNone(
            StaticIPAddress.objects.filter(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip
            ).first()
        )

    def test_creates_lease_for_unknown_interface(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(action="commit", ip=ip)
        update_lease(**kwargs)
        unknown_interface = UnknownInterface.objects.filter(
            mac_address=kwargs["mac"]
        ).first()
        self.assertIsNotNone(unknown_interface)
        self.assertEqual(subnet.vlan, unknown_interface.vlan)
        sip = unknown_interface.ip_addresses.first()
        self.assertIsNotNone(sip)
        self.assertEqual(sip.alloc_type, IPADDRESS_TYPE.DISCOVERED)
        self.assertEqual(sip.ip, ip)
        self.assertEqual(sip.subnet, subnet)
        self.assertEqual(sip.lease_time, kwargs["lease_time"])

        t0 = datetime.fromtimestamp(kwargs["timestamp"])
        self.assertEqual(sip.created, t0)
        self.assertEqual(sip.updated, t0)

    def test_create_ignores_none_hostname(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        hostname = "(none)"
        kwargs = self.make_kwargs(action="commit", ip=ip, hostname=hostname)
        update_lease(**kwargs)
        unknown_interface = UnknownInterface.objects.filter(
            mac_address=kwargs["mac"]
        ).first()
        self.assertIsNotNone(unknown_interface)
        self.assertEqual(subnet.vlan, unknown_interface.vlan)
        sip = unknown_interface.ip_addresses.first()
        self.assertIsNotNone(sip)
        self.assertEqual(sip.alloc_type, IPADDRESS_TYPE.DISCOVERED)
        self.assertEqual(sip.ip, ip)
        self.assertEqual(sip.subnet, subnet)
        self.assertEqual(sip.lease_time, kwargs["lease_time"])

        t0 = datetime.fromtimestamp(kwargs["timestamp"])
        self.assertEqual(sip.created, t0)
        self.assertEqual(sip.updated, t0)
        # No DNS record should have been crated.
        self.assertEqual(0, DNSResource.objects.count())

    def test_creates_dns_record_for_hostname(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        hostname = factory.make_name().lower()
        kwargs = self.make_kwargs(action="commit", ip=ip, hostname=hostname)
        update_lease(**kwargs)
        unknown_interface = UnknownInterface.objects.filter(
            mac_address=kwargs["mac"]
        ).first()
        self.assertIsNotNone(unknown_interface)
        self.assertEqual(subnet.vlan, unknown_interface.vlan)
        sip = unknown_interface.ip_addresses.first()
        self.assertIsNotNone(sip)
        dnsrr = get_one(DNSResource.objects.filter(name=hostname))
        self.assertIn(dnsrr, sip.dnsresource_set.all())

    def test_mutiple_calls_reuse_existing_staticipaddress_records(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        hostname = factory.make_name().lower()
        kwargs = self.make_kwargs(action="commit", ip=ip, hostname=hostname)
        update_lease(**kwargs)
        sip1 = StaticIPAddress.objects.get(ip=ip)
        update_lease(**kwargs)
        sip2 = StaticIPAddress.objects.get(ip=ip)
        self.assertEqual(sip2.id, sip1.id)

    def test_skips_dns_record_for_hostname_from_existing_node(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        hostname = factory.make_name().lower()
        factory.make_Node(hostname=hostname)
        kwargs = self.make_kwargs(action="commit", ip=ip, hostname=hostname)
        update_lease(**kwargs)
        unknown_interface = UnknownInterface.objects.filter(
            mac_address=kwargs["mac"]
        ).first()
        self.assertIsNotNone(unknown_interface)
        self.assertEqual(subnet.vlan, unknown_interface.vlan)
        sip = unknown_interface.ip_addresses.first()
        self.assertIsNotNone(sip)
        self.assertNotIn(sip, sip.dnsresource_set.all())

    def test_skips_dns_record_for_coerced_hostname_from_existing_node(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        hostname = "gaming device"
        factory.make_Node(hostname="gaming-device")
        kwargs = self.make_kwargs(action="commit", ip=ip, hostname=hostname)
        update_lease(**kwargs)
        unknown_interface = UnknownInterface.objects.filter(
            mac_address=kwargs["mac"]
        ).first()
        self.assertIsNotNone(unknown_interface)
        self.assertEqual(subnet.vlan, unknown_interface.vlan)
        sip = unknown_interface.ip_addresses.first()
        self.assertIsNotNone(sip)
        self.assertNotIn(sip, sip.dnsresource_set.all())

    def test_creates_lease_for_physical_interface(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        mac = factory.make_mac_address(padding=False)
        norm_mac = normalise_macaddress(mac)
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, address=norm_mac
        )
        boot_interface = node.get_boot_interface()
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(
            action="commit",
            mac=mac,
            ip=ip,
        )
        update_lease(**kwargs)

        sip = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip
        ).first()
        self.assertEqual(sip.alloc_type, IPADDRESS_TYPE.DISCOVERED)
        self.assertEqual(sip.ip, ip)
        self.assertEqual(sip.subnet, subnet)
        self.assertEqual(sip.lease_time, kwargs["lease_time"])

        t0 = datetime.fromtimestamp(kwargs["timestamp"])
        self.assertEqual(sip.created, t0)
        self.assertEqual(sip.updated, t0)
        self.assertCountEqual(
            [boot_interface.id], sip.interface_set.values_list("id", flat=True)
        )
        self.assertEqual(
            1,
            StaticIPAddress.objects.filter_by_ip_family(
                subnet.get_ipnetwork().version
            )
            .filter(
                alloc_type=IPADDRESS_TYPE.DISCOVERED, interface=boot_interface
            )
            .count(),
            "Interface should only have one DISCOVERED IP address.",
        )

    def test_creates_lease_for_physical_interface_keeps_other_ip_family(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface = node.get_boot_interface()
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(
            action="commit", mac=boot_interface.mac_address, ip=ip
        )

        # Make DISCOVERED in the other address family to make sure it is
        # not removed.
        network = subnet.get_ipnetwork()
        if network.version == IPADDRESS_FAMILY.IPv4:
            other_network = factory.make_ipv6_network()
        else:
            other_network = factory.make_ipv4_network()
        other_subnet = factory.make_Subnet(cidr=str(other_network.cidr))
        other_ip = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip="",
            subnet=other_subnet,
            interface=boot_interface,
        )

        update_lease(**kwargs)
        self.assertIsNotNone(
            reload_object(other_ip),
            "DISCOVERED IP address from the other address family should not "
            "have been deleted.",
        )

    def test_creates_lease_for_bond_interface(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface = node.get_boot_interface()
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)

        bond_interface = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            mac_address=boot_interface.mac_address,
            parents=[boot_interface],
        )

        kwargs = self.make_kwargs(
            action="commit", mac=bond_interface.mac_address, ip=ip
        )
        update_lease(**kwargs)

        sip = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=ip
        ).first()
        self.assertEqual(sip.alloc_type, IPADDRESS_TYPE.DISCOVERED)
        self.assertEqual(sip.ip, ip)
        self.assertEqual(sip.subnet, subnet)
        self.assertEqual(sip.lease_time, kwargs["lease_time"])

        t0 = datetime.fromtimestamp(kwargs["timestamp"])
        self.assertEqual(sip.created, t0)
        self.assertEqual(sip.updated, t0)
        self.assertCountEqual(
            [boot_interface.id, bond_interface.id],
            sip.interface_set.values_list("id", flat=True),
        )

    def test_release_removes_lease_keeps_discovered_subnet(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface = node.get_boot_interface()
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(
            action="release", mac=boot_interface.mac_address, ip=ip
        )
        update_lease(**kwargs)

        sip = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=None,
            subnet=subnet,
            interface=boot_interface,
        ).first()
        self.assertIsNotNone(
            sip,
            "DISCOVERED IP address shold have been created without an "
            "IP address.",
        )
        self.assertCountEqual(
            [boot_interface.id], sip.interface_set.values_list("id", flat=True)
        )

    def test_expiry_removes_lease_keeps_discovered_subnet(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface = node.get_boot_interface()
        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs = self.make_kwargs(
            action="expiry", mac=boot_interface.mac_address, ip=ip
        )
        update_lease(**kwargs)

        sip = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip=None,
            subnet=subnet,
            interface=boot_interface,
        ).first()
        self.assertIsNotNone(
            sip,
            "DISCOVERED IP address shold have been created without an "
            "IP address.",
        )
        self.assertCountEqual(
            [boot_interface.id], sip.interface_set.values_list("id", flat=True)
        )

    def test_expiry_does_not_keep_adding_null_ip_records_repeated_calls(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        # Create a bunch of null IPs to show the effects of bug 1817056.
        null_ips = [
            StaticIPAddress(
                created=timezone.now(),
                updated=timezone.now(),
                ip=None,
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                subnet=subnet,
            )
            for _ in range(10)
        ]
        StaticIPAddress.objects.bulk_create(null_ips)
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface = node.get_boot_interface()
        boot_interface.ip_addresses.add(*null_ips)

        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)

        kwargs = self.make_kwargs(
            action="expiry", mac=boot_interface.mac_address, ip=ip
        )
        null_ip_query = StaticIPAddress.objects.filter(
            alloc_type=IPADDRESS_TYPE.DISCOVERED, ip=None, subnet=subnet
        )
        update_lease(**kwargs)
        # XXX: We shouldn't need to record the previous count and
        #      instead expect the count to be 1. This will be addressed
        #      in bug 1817305.
        previous_null_ip_count = null_ip_query.count()
        previous_interface_ip_count = boot_interface.ip_addresses.count()
        update_lease(**kwargs)
        self.assertEqual(previous_null_ip_count, null_ip_query.count())
        self.assertEqual(
            previous_interface_ip_count, boot_interface.ip_addresses.count()
        )

    def test_expiry_does_not_keep_adding_null_ip_records_other_interface(self):
        subnet = factory.make_ipv4_Subnet_with_IPRanges(
            with_static_range=False, dhcp_on=True
        )
        node1 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface1 = node1.get_boot_interface()
        node2 = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        boot_interface2 = node2.get_boot_interface()
        # We now have two nodes, both having null IP records linking
        # them to the same subnet.
        self.assertIsNone(boot_interface1.ip_addresses.first().ip)
        self.assertIsNone(boot_interface2.ip_addresses.first().ip)

        dynamic_range = subnet.get_dynamic_ranges()[0]
        ip = factory.pick_ip_in_IPRange(dynamic_range)
        kwargs1 = self.make_kwargs(
            action="expiry", mac=boot_interface1.mac_address, ip=ip
        )
        kwargs2 = self.make_kwargs(
            action="expiry", mac=boot_interface2.mac_address, ip=ip
        )
        self.assertEqual(1, boot_interface1.ip_addresses.count())
        self.assertEqual(1, boot_interface2.ip_addresses.count())

        # When expiring the leases for the two nodes, they keep the
        # existing links they have.
        previous_ip_id1 = boot_interface1.ip_addresses.first().id
        previous_ip_id2 = boot_interface2.ip_addresses.first().id
        update_lease(**kwargs1)
        update_lease(**kwargs2)

        [ip_address1] = boot_interface1.ip_addresses.all()
        self.assertEqual(previous_ip_id1, ip_address1.id)
        self.assertEqual(1, ip_address1.interface_set.count())
        [ip_address2] = boot_interface2.ip_addresses.all()
        self.assertEqual(previous_ip_id2, ip_address2.id)
        self.assertEqual(1, ip_address2.interface_set.count())
        self.assertEqual(1, boot_interface1.ip_addresses.count())
        self.assertEqual(1, boot_interface2.ip_addresses.count())
