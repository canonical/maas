# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Subnet forms."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import random

from maasserver.forms_subnet import SubnetForm
from maasserver.models.fabric import Fabric
from maasserver.models.space import Space
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure


class TestSubnetForm(MAASServerTestCase):

    def test__requires_cidr(self):
        form = SubnetForm({})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "cidr": ["This field is required."],
            }, form.errors)

    def test__creates_subnet(self):
        subnet_name = factory.make_name("subnet")
        vlan = factory.make_VLAN()
        space = factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        gateway_ip = factory.pick_ip_in_network(network)
        dns_servers = []
        for _ in range(2):
            dns_servers.append(
                factory.pick_ip_in_network(
                    network, but_not=[gateway_ip] + dns_servers))
        form = SubnetForm({
            "name": subnet_name,
            "vlan": vlan.id,
            "space": space.id,
            "cidr": cidr,
            "gateway_ip": gateway_ip,
            "dns_servers": ','.join(dns_servers),
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=subnet_name, vlan=vlan, space=space, cidr=cidr,
                gateway_ip=gateway_ip, dns_servers=dns_servers))

    def test__creates_subnet_name_equal_to_cidr(self):
        vlan = factory.make_VLAN()
        space = factory.make_Space()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "vlan": vlan.id,
            "space": space.id,
            "cidr": cidr,
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=cidr, vlan=vlan, space=space, cidr=cidr))

    def test__creates_subnet_in_default_space(self):
        vlan = factory.make_VLAN()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "vlan": vlan.id,
            "cidr": cidr,
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=cidr, vlan=vlan, cidr=cidr,
                space=Space.objects.get_default_space()))

    def test__creates_subnet_in_default_fabric_and_vlan(self):
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=cidr, cidr=cidr,
                vlan=Fabric.objects.get_default_fabric().get_default_vlan(),
                space=Space.objects.get_default_space()))

    def test__creates_subnet_in_default_vlan_in_fabric(self):
        fabric = factory.make_Fabric()
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
            "fabric": fabric.id,
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=cidr, cidr=cidr,
                vlan=fabric.get_default_vlan(),
                space=Space.objects.get_default_space()))

    def test__creates_subnet_in_default_fabric_with_vid(self):
        vlan = factory.make_VLAN(fabric=Fabric.objects.get_default_fabric())
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
            "vid": vlan.vid,
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=cidr, cidr=cidr,
                vlan=vlan,
                space=Space.objects.get_default_space()))

    def test__creates_subnet_in_fabric_with_vid(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
            "fabric": fabric.id,
            "vid": vlan.vid,
        })
        self.assertTrue(form.is_valid(), form.errors)
        subnet = form.save()
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=cidr, cidr=cidr,
                vlan=vlan,
                space=Space.objects.get_default_space()))

    def test__error_for_unknown_vid_in_default_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=fabric)
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
            "vid": vlan.vid,
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "vid": ["No VLAN with vid %s in default fabric." % vlan.vid]
            }, form.errors)

    def test__error_for_unknown_vid_in_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=Fabric.objects.get_default_fabric())
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
            "fabric": fabric.id,
            "vid": vlan.vid,
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "vid": ["No VLAN with vid %s in fabric %s." % (vlan.vid, fabric)]
            }, form.errors)

    def test__error_for_vlan_not_in_fabric(self):
        fabric = factory.make_Fabric()
        vlan = factory.make_VLAN(fabric=Fabric.objects.get_default_fabric())
        network = factory.make_ip4_or_6_network()
        cidr = unicode(network.cidr)
        form = SubnetForm({
            "cidr": cidr,
            "fabric": fabric.id,
            "vlan": vlan.id,
        })
        self.assertFalse(form.is_valid(), form.errors)
        self.assertEquals({
            "vlan": ["VLAN %s is not in fabric %s." % (vlan, fabric)]
            }, form.errors)

    def test__doest_require_vlan_space_or_cidr_on_update(self):
        subnet = factory.make_Subnet()
        form = SubnetForm(instance=subnet, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_subnet(self):
        new_name = factory.make_name("subnet")
        subnet = factory.make_Subnet()
        new_vlan = factory.make_VLAN()
        new_space = factory.make_Space()
        new_network = factory.make_ip4_or_6_network()
        new_cidr = unicode(new_network.cidr)
        new_gateway_ip = factory.pick_ip_in_network(new_network)
        new_dns_servers = []
        for _ in range(2):
            new_dns_servers.append(
                factory.pick_ip_in_network(
                    new_network, but_not=[new_gateway_ip] + new_dns_servers))
        form = SubnetForm(instance=subnet, data={
            "name": new_name,
            "vlan": new_vlan.id,
            "space": new_space.id,
            "cidr": new_cidr,
            "gateway_ip": new_gateway_ip,
            "dns_servers": ','.join(new_dns_servers),
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        subnet = reload_object(subnet)
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=new_name, vlan=new_vlan, space=new_space, cidr=new_cidr,
                gateway_ip=new_gateway_ip, dns_servers=new_dns_servers))

    def test__updates_subnet_name_to_cidr(self):
        subnet = factory.make_Subnet()
        subnet.name = subnet.cidr
        subnet.save()
        new_network = factory.make_ip4_or_6_network()
        new_cidr = unicode(new_network.cidr)
        new_gateway_ip = factory.pick_ip_in_network(new_network)
        form = SubnetForm(instance=subnet, data={
            "cidr": new_cidr,
            "gateway_ip": new_gateway_ip,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        subnet = reload_object(subnet)
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=new_cidr, cidr=new_cidr, gateway_ip=new_gateway_ip))

    def test__doesnt_overwrite_other_fields(self):
        new_name = factory.make_name("subnet")
        subnet = factory.make_Subnet()
        form = SubnetForm(instance=subnet, data={
            "name": new_name,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        subnet = reload_object(subnet)
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                name=new_name, vlan=subnet.vlan, space=subnet.space,
                cidr=subnet.cidr, gateway_ip=subnet.gateway_ip,
                dns_servers=subnet.dns_servers))

    def test__clears_gateway_and_dns_ervers(self):
        subnet = factory.make_Subnet()
        form = SubnetForm(instance=subnet, data={
            "gateway_ip": "",
            "dns_servers": "",
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        subnet = reload_object(subnet)
        self.assertThat(
            subnet, MatchesStructure.byEquality(
                gateway_ip=None, dns_servers=[]))

    def test__clean_dns_servers_accepts_comma_separated_list(self):
        subnet = factory.make_Subnet()
        dns_servers = [factory.make_ip_address()
                       for _ in range(random.randint(2, 10))]
        form = SubnetForm(instance=subnet, data={
            "dns_servers": ','.join(dns_servers)
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        subnet = reload_object(subnet)
        self.assertEquals(dns_servers,
                          subnet.dns_servers)

    def test__clean_dns_servers_accepts_space_separated_list(self):
        subnet = factory.make_Subnet()
        dns_servers = [factory.make_ip_address()
                       for _ in range(random.randint(2, 10))]
        form = SubnetForm(instance=subnet, data={
            "dns_servers": " ".join(dns_servers)
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        subnet = reload_object(subnet)
        self.assertEquals(dns_servers,
                          subnet.dns_servers)
