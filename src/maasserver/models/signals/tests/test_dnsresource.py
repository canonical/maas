# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of dnsresource signals."""

from maasserver.models import DNSPublication
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPostSaveDNSResourceSignal(MAASServerTestCase):
    def test_save_dnsresource_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300, ip_addresses=[]
        )
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            "zone example.com added resource maas", dnspublication.source
        )


class TestPostDeleteDNSResourceSignal(MAASServerTestCase):
    def test_delete_dnsresource(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300
        )
        dnsresource.delete()
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            "zone example.com removed resource maas", dnspublication.source
        )


class TestUpdateDNSResourceSignal(MAASServerTestCase):
    def test_update_dnsresource_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        new_domain = factory.make_Domain("newexample.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300
        )
        dnsresource.domain = new_domain
        dnsresource.name = "maas-updated"
        dnsresource.address_ttl = 600
        dnsresource.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertIn(
            "resource maas-updated moved to newexample.com",
            dnspublication.source,
        )
        self.assertIn("updated resource maas-updated", dnspublication.source)


class TestLinkDNSResourceSignal(MAASServerTestCase):
    def test_link_dnsresource_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300
        )

        subnet = factory.make_Subnet()
        staticip = factory.make_StaticIPAddress(subnet=subnet)

        dnsresource.ip_addresses.add(staticip)

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            f"ip {staticip.ip} linked to resource maas on zone example.com",
            dnspublication.source,
        )

    def test_unlink_dnsresource_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300
        )

        subnet = factory.make_Subnet()
        staticip = factory.make_StaticIPAddress(subnet=subnet)

        dnsresource.ip_addresses.add(staticip)
        dnsresource.ip_addresses.remove(staticip)

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            f"ip {staticip.ip} unlinked from resource maas on zone example.com",
            dnspublication.source,
        )
