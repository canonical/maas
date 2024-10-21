# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Subnet forms."""


import random

from maasserver.forms.subnet import SubnetForm
from maasserver.models.fabric import Fabric
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from provisioningserver.boot import BootMethodRegistry


class TestSubnetForm(MAASServerTestCase):
    def test_requires_cidr(self):
        form = SubnetForm({})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"cidr": ["This field is required."]}, dict(form.errors)
        )

    def test_rejects_provided_space_on_update(self):
        space = factory.make_Space()
        subnet = factory.make_Subnet()
        form = SubnetForm(instance=subnet, data={"space": space.id})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {
                "space": [
                    "Spaces may no longer be set on subnets. Set the space on the "
                    "underlying VLAN."
                ]
            },
            dict(form.errors),
        )

    def test_rejects_space_on_create(self):
        space = factory.make_Space()
        form = SubnetForm(
            {"space": space.id, "cidr": factory._make_random_network()}
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {
                "space": [
                    "Spaces may no longer be set on subnets. Set the space on the "
                    "underlying VLAN."
                ]
            },
            dict(form.errors),
        )

    def test_rejects_invalid_cidr(self):
        form = SubnetForm(
            {"cidr": "ten dot zero dot zero dot zero slash zero"}
        )
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"cidr": ["Required format: <network>/<prefixlen>."]},
            dict(form.errors),
        )

    def test_rejects_ipv4_cidr_with_zero_prefixlen(self):
        form = SubnetForm({"cidr": "0.0.0.0/0"})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"cidr": ["Prefix length must be greater than 0."]},
            dict(form.errors),
        )

    def test_rejects_ipv6_cidr_with_zero_prefixlen(self):
        form = SubnetForm({"cidr": "::/0"})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"cidr": ["Prefix length must be greater than 0."]},
            dict(form.errors),
        )

    def test_creates_subnet(self):
        subnet_name = factory.make_name("subnet")
        subnet_description = factory.make_name("description")
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers
                )
            )
        form = SubnetForm(
            {
                "name": subnet_name,
                "description": subnet_description,
                "vlan": vlan.id,
                "cidr": cidr,
                "gateway_ip": gateway_ip,
                "dns_servers": ",".join(dns_servers),
            }
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual(subnet.name, subnet_name)
        self.assertEqual(subnet.description, subnet_description)
        self.assertEqual(subnet.vlan, vlan)
        self.assertEqual(subnet.cidr, cidr)
        self.assertEqual(subnet.gateway_ip, gateway_ip)
        self.assertEqual(subnet.dns_servers, dns_servers)

    def test_removes_host_bits_and_whitespace(self):
        form = SubnetForm({"cidr": " 10.0.0.1/24 "})
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual("10.0.0.0/24", subnet.cidr)

    def test_creates_subnet_name_equal_to_cidr(self):
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"vlan": vlan.id, "cidr": cidr})
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual(subnet.name, cidr)
        self.assertEqual(subnet.vlan, vlan)
        self.assertEqual(subnet.cidr, cidr)

    def test_creates_subnet_in_default_fabric_and_vlan(self):
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"cidr": cidr})
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual(subnet.name, cidr)
        self.assertEqual(subnet.cidr, cidr)
        self.assertEqual(
            subnet.vlan, Fabric.objects.get_default_fabric().get_default_vlan()
        )

    def test_creates_subnet_in_default_vlan_in_fabric(self):
        fabric = factory.make_Fabric()
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"cidr": cidr, "fabric": fabric.id, "vlan": None})
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual(subnet.name, cidr)
        self.assertEqual(subnet.cidr, cidr)
        self.assertEqual(subnet.vlan, fabric.get_default_vlan())

    def test_creates_subnet_in_default_fabric_with_vid(self):
        vlan = factory.make_VLAN(fabric=Fabric.objects.get_default_fabric())
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"cidr": cidr, "vid": vlan.vid, "vlan": None})
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual(subnet.name, cidr)
        self.assertEqual(subnet.cidr, cidr)
        self.assertEqual(subnet.vlan, vlan)

    def test_creates_subnet_in_fabric_with_vid(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm(
            {"cidr": cidr, "fabric": fabric.id, "vid": vlan.vid, "vlan": None}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        subnet = form.save()
        self.assertEqual(subnet.name, cidr)
        self.assertEqual(subnet.cidr, cidr)
        self.assertEqual(subnet.vlan, vlan)

    def test_error_for_unknown_vid_in_default_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"cidr": cidr, "vid": vlan.vid})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"vid": ["No VLAN with vid %s in default fabric." % vlan.vid]},
            dict(form.errors),
        )

    def test_error_for_unknown_vid_in_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=Fabric.objects.get_default_fabric())
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"cidr": cidr, "fabric": fabric.id, "vid": vlan.vid})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"vid": [f"No VLAN with vid {vlan.vid} in fabric {fabric}."]},
            dict(form.errors),
        )

    def test_error_for_vlan_not_in_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=Fabric.objects.get_default_fabric())
        network = factory.make_ip4_or_6_network()
        cidr = str(network.cidr)
        form = SubnetForm({"cidr": cidr, "fabric": fabric.id, "vlan": vlan.id})
        self.assertFalse(form.is_valid(), dict(form.errors))
        self.assertEqual(
            {"vlan": [f"VLAN {vlan} is not in fabric {fabric}."]},
            dict(form.errors),
        )

    def test_doest_require_vlan_or_cidr_on_update(self):
        subnet = factory.make_Subnet()
        form = SubnetForm(instance=subnet, data={})
        self.assertTrue(form.is_valid(), dict(form.errors))

    def test_updates_subnet(self):
        new_name = factory.make_name("subnet")
        new_description = factory.make_name("description")
        subnet = factory.make_Subnet()
        new_vlan = factory.make_VLAN()
        new_network = factory.make_ip4_or_6_network()
        new_cidr = str(new_network.cidr)
        new_gateway_ip = factory.pick_ip_in_network(new_network)
        new_dns_servers = []
        for _ in range(2):
            new_dns_servers.append(
                factory.pick_ip_in_network(
                    new_network, but_not=[new_gateway_ip] + new_dns_servers
                )
            )
        form = SubnetForm(
            instance=subnet,
            data={
                "name": new_name,
                "description": new_description,
                "vlan": new_vlan.id,
                "cidr": new_cidr,
                "gateway_ip": new_gateway_ip,
                "dns_servers": ",".join(new_dns_servers),
            },
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertEqual(subnet.name, new_name)
        self.assertEqual(subnet.description, new_description)
        self.assertEqual(subnet.vlan, new_vlan)
        self.assertEqual(subnet.cidr, new_cidr)
        self.assertEqual(subnet.gateway_ip, new_gateway_ip)
        self.assertEqual(subnet.dns_servers, new_dns_servers)

    def test_updates_subnet_name_to_cidr(self):
        subnet = factory.make_Subnet()
        subnet.name = subnet.cidr
        subnet.save()
        new_network = factory.make_ip4_or_6_network()
        new_cidr = str(new_network.cidr)
        new_gateway_ip = factory.pick_ip_in_network(new_network)
        form = SubnetForm(
            instance=subnet,
            data={"cidr": new_cidr, "gateway_ip": new_gateway_ip},
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertEqual(subnet.name, new_cidr)
        self.assertEqual(subnet.cidr, new_cidr)
        self.assertEqual(subnet.gateway_ip, new_gateway_ip)

    def test_updates_subnet_cidr_with_reserved_ips(self):
        interface = factory.make_Interface()
        subnet = factory.make_Subnet(cidr="10.0.0.0/24")
        factory.make_ReservedIP(
            ip="10.0.0.200", mac_address=interface.mac_address, subnet=subnet
        )
        form = SubnetForm(
            instance=subnet,
            data={"cidr": "10.0.0.0/28"},
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(
            {
                "cidr": [
                    "The new subnet CIDR would exclude the reserved ip 10.0.0.200. Please remove it first."
                ]
            },
            form.errors,
        )

    def test_updates_subnet_name_doesnt_remove_dns_server(self):
        # Regression test for lp:1521833
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(2, 10))
        ]
        subnet = factory.make_Subnet(dns_servers=dns_servers)
        form = SubnetForm(
            instance=subnet, data={"name": factory.make_name("subnet")}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertEqual(dns_servers, subnet.dns_servers)

    def test_doesnt_overwrite_other_fields(self):
        new_name = factory.make_name("subnet")
        original_subnet = factory.make_Subnet()
        form = SubnetForm(instance=original_subnet, data={"name": new_name})
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(original_subnet)
        self.assertEqual(subnet.name, new_name)
        self.assertEqual(subnet.vlan, original_subnet.vlan)
        self.assertEqual(subnet.cidr, original_subnet.cidr)
        self.assertEqual(subnet.gateway_ip, original_subnet.gateway_ip)
        self.assertEqual(subnet.dns_servers, original_subnet.dns_servers)

    def test_clears_gateway_and_dns_ervers(self):
        subnet = factory.make_Subnet()
        form = SubnetForm(
            instance=subnet, data={"gateway_ip": "", "dns_servers": ""}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertIsNone(subnet.gateway_ip)
        self.assertEqual(subnet.dns_servers, [])

    def test_clean_dns_servers_accepts_comma_separated_list(self):
        subnet = factory.make_Subnet()
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(2, 10))
        ]
        form = SubnetForm(
            instance=subnet, data={"dns_servers": ",".join(dns_servers)}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertEqual(dns_servers, subnet.dns_servers)

    def test_clean_dns_servers_accepts_space_separated_list(self):
        subnet = factory.make_Subnet()
        dns_servers = [
            factory.make_ip_address() for _ in range(random.randint(2, 10))
        ]
        form = SubnetForm(
            instance=subnet, data={"dns_servers": " ".join(dns_servers)}
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertEqual(dns_servers, subnet.dns_servers)

    def test_clean_disabled_boot_arches_name_comma_seperated_list(self):
        subnet = factory.make_Subnet()
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.user_class
            ],
            3,
        )

        form = SubnetForm(
            instance=subnet,
            data={"disabled_boot_architectures": ",".join(disabled_arches)},
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertCountEqual(
            disabled_arches, subnet.disabled_boot_architectures
        )

    def test_clean_disabled_boot_arches_name_space_seperated_list(self):
        subnet = factory.make_Subnet()
        disabled_arches = random.sample(
            [
                boot_method.name
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet or boot_method.user_class
            ],
            3,
        )

        form = SubnetForm(
            instance=subnet,
            data={"disabled_boot_architectures": " ".join(disabled_arches)},
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertCountEqual(
            disabled_arches, subnet.disabled_boot_architectures
        )

    def test_clean_disabled_boot_arches_octet(self):
        subnet = factory.make_Subnet()
        disabled_arches = random.sample(
            [
                boot_method
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet
            ],
            3,
        )
        form = SubnetForm(
            instance=subnet,
            data={
                "disabled_boot_architectures": ",".join(
                    [bm.arch_octet for bm in disabled_arches]
                )
            },
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertCountEqual(
            [bm.name for bm in disabled_arches],
            subnet.disabled_boot_architectures,
        )

    def test_clean_disabled_boot_arches_hex(self):
        subnet = factory.make_Subnet()
        disabled_arches = random.sample(
            [
                boot_method
                for _, boot_method in BootMethodRegistry
                if boot_method.arch_octet
            ],
            3,
        )
        form = SubnetForm(
            instance=subnet,
            data={
                "disabled_boot_architectures": ",".join(
                    [
                        bm.arch_octet.replace("00:", "0x")
                        for bm in disabled_arches
                    ]
                )
            },
        )
        self.assertTrue(form.is_valid(), dict(form.errors))
        form.save()
        subnet = reload_object(subnet)
        self.assertCountEqual(
            [bm.name for bm in disabled_arches],
            subnet.disabled_boot_architectures,
        )

    def test_clean_disabled_boot_arches_cannot_disable_fake_boot_arch(self):
        # The Windows boot loader responds to bootloader configuration requests
        # but isc-dhcpd is not configured to respond to a boot octet nor a
        # user-class. Thus it is unable to be disabled.
        subnet = factory.make_Subnet(disabled_boot_architectures=[])
        choices = [
            boot_method.name
            for _, boot_method in BootMethodRegistry
            if not boot_method.arch_octet and not boot_method.user_class
        ]

        form = SubnetForm(
            instance=subnet,
            data={"disabled_boot_architectures": random.choice(choices)},
        )
        self.assertFalse(form.is_valid())
        subnet = reload_object(subnet)
        self.assertEqual([], subnet.disabled_boot_architectures)

    def test_clean_disabled_detects_invalid_arch(self):
        subnet = factory.make_Subnet(disabled_boot_architectures=[])
        form = SubnetForm(
            instance=subnet,
            data={
                "disabled_boot_architectures": factory.make_name("boot_arch")
            },
        )
        self.assertFalse(form.is_valid())
        subnet = reload_object(subnet)
        self.assertEqual([], subnet.disabled_boot_architectures)
