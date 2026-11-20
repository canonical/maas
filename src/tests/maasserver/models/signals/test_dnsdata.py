# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the behaviour of dnsresource signals."""

from maasserver.models import DNSPublication
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestPostSaveDNSDataSignal(MAASServerTestCase):
    def test_save_dnsdata_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300, ip_addresses=[]
        )
        factory.make_DNSData(
            dnsresource=dnsresource,
            rrtype="TXT",
            rrdata="U29ycnkgZm9yIHRoaXMh",
        )
        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            "added TXT to resource maas on zone example.com",
            dnspublication.source,
        )


class TestPostDeleteSubnetSignal(MAASServerTestCase):
    def test_delete_dnsresource(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300
        )
        dnsdata = factory.make_DNSData(
            dnsresource=dnsresource,
            rrtype="TXT",
            rrdata="U29ycnkgZm9yIHRoaXMh",
        )
        dnsdata.delete()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            "removed TXT from resource maas on zone example.com",
            dnspublication.source,
        )


class TestUpdateDNSDataSignal(MAASServerTestCase):
    def test_update_dnsdata_creates_dnspublication(self):
        domain = factory.make_Domain("example.com", authoritative=True)
        dnsresource = factory.make_DNSResource(
            domain=domain, name="maas", address_ttl=300
        )
        dnsdata = factory.make_DNSData(
            dnsresource=dnsresource,
            rrtype="TXT",
            rrdata="U29ycnkgZm9yIHRoaXMh",
        )
        dnsdata.rrdata = "a2l3aQ=="
        dnsdata.save()

        dnspublication = DNSPublication.objects.get_most_recent()
        self.assertEqual(
            "updated TXT in resource maas on zone example.com",
            dnspublication.source,
        )
