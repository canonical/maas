# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of node signals."""

__all__ = []

import random

from django.conf import settings
from maasserver.dns import config as dns_config_module
from maasserver.models import domain as domain_module
from maasserver.models.config import Config
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCallsMatch,
    MockNotCalled,
)
from mock import call
from netaddr import IPNetwork


class TestDNSSignals(MAASServerTestCase):
    """Test that signals work for various DNS changes."""

    def test_saving_domain_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_add_domains = self.patch_autospec(
            dns_config_module, "dns_add_domains")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        domain = factory.make_Domain()
        self.assertThat(dns_add_domains, MockCalledOnceWith(domains={domain}))
        self.assertThat(dns_update_all_zones, MockNotCalled())
        domain.name = factory.make_name("domain")
        domain.save()
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())

    def test_saving_dnsresource_triggers_update(self):
        domain = factory.make_Domain()
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dnsrr = factory.make_DNSResource(domain=domain)
        # Once from saving the DNSResource, and once from adding the
        # StaticIPAddress.
        self.expectThat(
            dns_update_domains, MockCallsMatch(
                call({domain}), call({domain})))
        subnet = dnsrr.ip_addresses.first().subnet
        self.assertThat(dns_update_subnets, MockCalledOnceWith({subnet}))
        self.assertEqual(2, dns_update_all_zones.call_count)
        dnsrr.name = factory.make_name("dnsresource")
        dnsrr.save()
        self.assertEqual(3, dns_update_all_zones.call_count)

    def test_saving_dnsresource_without_ip_triggers_update(self):
        domain = factory.make_Domain()
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dnsrr = factory.make_DNSResource(domain=domain, no_ip_addresses=True)
        self.assertThat(
            dns_update_domains, MockCalledOnceWith(domains={domain}))
        self.assertThat(dns_update_subnets, MockNotCalled())
        self.assertThat(dns_update_all_zones, MockNotCalled())
        dnsrr.name = factory.make_name("dnsresource")
        dnsrr.save()
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())

    def test_saving_dnsdata_triggers_update(self):
        dnsrr = factory.make_DNSResource(no_ip_addresses=True)
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dnsdata = factory.make_DNSData(dnsresource=dnsrr)
        self.assertThat(
            dns_update_domains, MockCalledOnceWith(domains={dnsrr.domain}))
        self.assertThat(dns_update_subnets, MockNotCalled())
        dnsdata.ttl = random.randint(0, 10000000)
        dnsdata.save()
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())

    def test_saving_subnet_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_add_subnets = self.patch_autospec(
            dns_config_module, "dns_add_subnets")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        subnet = factory.make_Subnet()
        self.assertThat(dns_add_subnets, MockCalledOnceWith(subnets={subnet}))
        subnet.name = factory.make_name("subnet")
        subnet.save()
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())

    def test_saving_subnet_with_parent_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_add_subnets = self.patch_autospec(
            dns_config_module, "dns_add_subnets")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        net = factory.make_ip4_or_6_network(host_bits=random.randint(2, 3))
        if net.version == 6:
            prefixlen = random.randint(121, 124)
        else:
            prefixlen = random.randint(20, 24)
        parent = IPNetwork("%s/%d" % (net.network, prefixlen))
        parent = IPNetwork("%s/%d" % (parent.network, prefixlen))
        parent_subnet = factory.make_Subnet(cidr=parent.cidr)
        self.assertThat(dns_add_subnets, MockCalledOnceWith(
            subnets={parent_subnet}))
        subnet = factory.make_Subnet(cidr=net.cidr)
        self.assertEqual(2, dns_add_subnets.call_count)
        self.assertThat(dns_update_subnets, MockCalledOnceWith(
            {parent_subnet}))
        subnet.name = factory.make_name("subnet")
        subnet.save()
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())

    def test_deleting_node_triggers_update(self):
        node = factory.make_Node()
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_by_node = self.patch_autospec(
            dns_config_module, "dns_update_by_node")
        node.delete()
        self.assertThat(dns_update_by_node, MockCalledOnceWith(node=node))

    def test_changing_hostname_triggers_update(self):
        node = factory.make_Node()
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_by_node = self.patch_autospec(
            dns_config_module, "dns_update_by_node")
        node.hostname = factory.make_name("hostname")
        node.save()
        self.assertThat(dns_update_by_node, MockCalledOnceWith(node=node))

    def test_changing_node_domain_triggers_update(self):
        node = factory.make_Node()
        domain = factory.make_Domain()
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_by_node = self.patch_autospec(
            dns_config_module, "dns_update_by_node")
        node.domain = domain
        node.save()
        self.assertThat(dns_update_by_node, MockCalledOnceWith(node=node))

    def test_changing_system_id_does_not_trigger_update(self):
        node = factory.make_Node()
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_by_node = self.patch_autospec(
            dns_config_module, "dns_update_by_node")
        node.system_id = factory.make_name('system_id')
        node.save()
        self.assertThat(dns_update_by_node, MockNotCalled())

    def test_changing_dns_settings_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        Config.objects.set_config('upstream_dns', '8.8.8.8')
        Config.objects.set_config('default_dns_ttl', '99')
        self.assertEqual(2, dns_update_all_zones.call_count)

    def test_changing_kms_host_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_kms_setting_changed = self.patch_autospec(
            domain_module, "dns_kms_setting_changed")
        Config.objects.set_config('windows_kms_host', '8.8.8.8')
        self.assertThat(dns_kms_setting_changed, MockCalledOnceWith())

    def test_adding_and_removing_ip_on_dnsrr_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        domain = factory.make_Domain()
        dnsrr = factory.make_DNSResource(domain=domain, no_ip_addresses=True)
        sip = factory.make_StaticIPAddress()
        self.assertThat(dns_update_subnets, MockNotCalled())
        self.assertThat(dns_update_domains, MockCalledOnceWith({domain}))
        dnsrr.ip_addresses.add(sip)
        self.assertThat(dns_update_all_zones, MockNotCalled())
        # One call from creating the DNSResource, and one from adding the
        # StaticIPAddress.
        self.assertThat(
            dns_update_domains,
            MockCallsMatch(call({domain}), call({domain})))
        # Once from adding the StaticIPAddress.
        self.assertThat(
            dns_update_subnets,
            MockCallsMatch(call({sip.subnet})))
        # Now remove it.
        dnsrr.ip_addresses.remove(sip)
        # Calls update_all_zones, does not generate new calls to the others.
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())
        self.assertEqual(2, dns_update_domains.call_count)
        self.assertEqual(1, dns_update_subnets.call_count)

    def test_adding_and_removing_ip_on_interface_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        self.assertThat(dns_update_all_zones, MockNotCalled())
        self.assertThat(
            dns_update_subnets, MockCallsMatch(
                call({subnet}), call({subnet})))
        self.assertThat(
            dns_update_domains, MockCallsMatch(
                call({node.domain}), call({node.domain})))
        # Now add an extra StaticIPAddress
        sip = factory.make_StaticIPAddress(subnet=subnet)
        node.get_boot_interface().ip_addresses.add(sip)
        # This calls dns_update_{domains,subnets}
        self.assertThat(dns_update_all_zones, MockNotCalled())
        self.assertThat(
            dns_update_subnets, MockCallsMatch(
                call({subnet}), call({subnet}), call({subnet})))
        self.assertThat(
            dns_update_domains, MockCallsMatch(
                call({node.domain}), call({node.domain}),
                call({node.domain})))
        # And then remove it
        node.get_boot_interface().ip_addresses.remove(sip)
        # This calls update_all_zones
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())
        self.assertEqual(3, dns_update_subnets.call_count)
        self.assertEqual(3, dns_update_domains.call_count)

    def test_adding_and_removing_dnsrr_on_ip_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        domain = factory.make_Domain()
        dnsrr = factory.make_DNSResource(domain=domain, no_ip_addresses=True)
        sip = factory.make_StaticIPAddress()
        self.assertThat(dns_update_subnets, MockNotCalled())
        self.assertThat(dns_update_domains, MockCalledOnceWith({domain}))
        sip.dnsresource_set.add(dnsrr)
        self.assertThat(dns_update_all_zones, MockNotCalled())
        # One call from creating the DNSResource, and one from adding the
        # StaticIPAddress.
        self.assertThat(
            dns_update_domains,
            MockCallsMatch(call({domain}), call({domain})))
        # Once from adding the StaticIPAddress.
        self.assertThat(
            dns_update_subnets,
            MockCallsMatch(call({sip.subnet})))
        # Now remove it.
        sip.dnsresource_set.remove(dnsrr)
        # Calls update_all_zones, does not generate new calls to the others.
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())
        self.assertEqual(2, dns_update_domains.call_count)
        self.assertEqual(1, dns_update_subnets.call_count)

    def test_adding_and_removing_interface_on_ip_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        dns_update_domains = self.patch_autospec(
            dns_config_module, "dns_update_domains")
        dns_update_subnets = self.patch_autospec(
            dns_config_module, "dns_update_subnets")
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(subnet=subnet)
        self.assertThat(dns_update_all_zones, MockNotCalled())
        self.assertThat(
            dns_update_subnets, MockCallsMatch(
                call({subnet}), call({subnet})))
        self.assertThat(
            dns_update_domains, MockCallsMatch(
                call({node.domain}), call({node.domain})))
        # Now add an extra StaticIPAddress
        sip = factory.make_StaticIPAddress(subnet=subnet)
        sip.interface_set.add(node.get_boot_interface())
        # This calls dns_update_{domains,subnets}
        self.assertThat(dns_update_all_zones, MockNotCalled())
        self.assertThat(
            dns_update_subnets, MockCallsMatch(
                call({subnet}), call({subnet}), call({subnet})))
        self.assertThat(
            dns_update_domains, MockCallsMatch(
                call({node.domain}), call({node.domain}),
                call({node.domain})))
        # And then remove it
        sip.interface_set.remove(node.get_boot_interface())
        # This calls update_all_zones
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())
        self.assertEqual(3, dns_update_subnets.call_count)
        self.assertEqual(3, dns_update_domains.call_count)
