# Copyright 2015 Canonical Ltd.  This software is licensed under the
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
    MockNotCalled,
)


class TestDNSSignals(MAASServerTestCase):
    """Test that signals work for various DNS changes."""

    def test_saving_domain_triggers_update(self):
        self.patch(settings, "DNS_CONNECT", False)
        dns_add_domains = self.patch_autospec(
            dns_config_module, "dns_add_domains")
        dns_update_all_zones = self.patch_autospec(
            dns_config_module, "dns_update_all_zones")
        domain = factory.make_Domain()
        self.assertThat(dns_add_domains, MockCalledOnceWith(domains=[domain]))
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
        self.assertThat(
            dns_update_domains, MockCalledOnceWith(domains=[domain]))
        self.assertThat(dns_update_subnets, MockNotCalled())
        self.assertThat(dns_update_all_zones, MockCalledOnceWith())
        dnsrr.name = factory.make_name("dnsresource")
        dnsrr.save()
        self.assertEqual(2, dns_update_all_zones.call_count)

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
            dns_update_domains, MockCalledOnceWith(domains=[domain]))
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
            dns_update_domains, MockCalledOnceWith(domains=[dnsrr.domain]))
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
        self.assertThat(dns_add_subnets, MockCalledOnceWith(subnets=[subnet]))
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
