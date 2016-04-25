# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DNSResource model."""

__all__ = []


import re

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models.dnsresource import (
    DNSResource,
    separate_fqdn,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools import ExpectedException
from testtools.matchers import MatchesStructure


class TestDNSResourceManagerGetDNSResourceOr404(MAASServerTestCase):

    def test__user_view_returns_dnsresource(self):
        user = factory.make_User()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, user, NODE_PERMISSION.VIEW))

    def test__user_edit_raises_PermissionError(self):
        user = factory.make_User()
        dnsresource = factory.make_DNSResource()
        self.assertRaises(
            PermissionDenied,
            DNSResource.objects.get_dnsresource_or_404,
            dnsresource.id, user, NODE_PERMISSION.EDIT)

    def test__user_admin_raises_PermissionError(self):
        user = factory.make_User()
        dnsresource = factory.make_DNSResource()
        self.assertRaises(
            PermissionDenied,
            DNSResource.objects.get_dnsresource_or_404,
            dnsresource.id, user, NODE_PERMISSION.ADMIN)

    def test__admin_view_returns_dnsresource(self):
        admin = factory.make_admin()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, admin, NODE_PERMISSION.VIEW))

    def test__admin_edit_returns_dnsresource(self):
        admin = factory.make_admin()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, admin, NODE_PERMISSION.EDIT))

    def test__admin_admin_returns_dnsresource(self):
        admin = factory.make_admin()
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            dnsresource,
            DNSResource.objects.get_dnsresource_or_404(
                dnsresource.id, admin, NODE_PERMISSION.ADMIN))


class TestDNSResourceManager(MAASServerTestCase):

    def test__default_specifier_matches_id(self):
        factory.make_DNSResource()
        dnsresource = factory.make_DNSResource()
        factory.make_DNSResource()
        id = dnsresource.id
        self.assertItemsEqual(
            DNSResource.objects.filter_by_specifiers('%s' % id),
            [dnsresource]
        )

    def test__default_specifier_matches_name(self):
        factory.make_DNSResource()
        name = factory.make_name('dnsresource')
        dnsresource = factory.make_DNSResource(name=name)
        factory.make_DNSResource()
        self.assertItemsEqual(
            DNSResource.objects.filter_by_specifiers(name),
            [dnsresource]
        )

    def test__name_specifier_matches_name(self):
        factory.make_DNSResource()
        name = factory.make_name('dnsresource')
        dnsresource = factory.make_DNSResource(name=name)
        factory.make_DNSResource()
        self.assertItemsEqual(
            DNSResource.objects.filter_by_specifiers('name:%s' % name),
            [dnsresource]
        )


class DNSResourceTest(MAASServerTestCase):

    def test_separate_fqdn_splits_srv(self):
        self.assertEqual(
            ("_sip._tcp.voip", "example.com"),
            separate_fqdn("_sip._tcp.voip.example.com", 'SRV'))

    def test_separate_fqdn_splits_nonsrv(self):
        self.assertEqual(
            ("foo", "test.example.com"),
            separate_fqdn("foo.test.example.com", 'A'))

    def test_separate_fqdn_returns_atsign_for_top_of_domain(self):
        name = "%s.%s.%s" % (
            factory.make_name("a"),
            factory.make_name("b"),
            factory.make_name("c"))
        factory.make_Domain(name=name)
        self.assertEqual(('@', name), separate_fqdn(name))

    def test_separate_fqdn_allows_domain_override(self):
        parent = "%s.%s" % (
            factory.make_name("b"),
            factory.make_name("c"))
        label = factory.make_name("a")
        name = "%s.%s" % (label, parent)
        factory.make_Domain(name=name)
        self.assertEqual(
            (label, parent), separate_fqdn(name, domainname=parent))

    def test_creates_dnsresource(self):
        name = factory.make_name('name')
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource_from_db = DNSResource.objects.get(name=name)
        self.assertThat(dnsresource_from_db, MatchesStructure.byEquality(
            name=name))

    def test_allows_atsign(self):
        name = '@'
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource_from_db = DNSResource.objects.get(name=name)
        self.assertThat(dnsresource_from_db, MatchesStructure.byEquality(
            name=name))

    def test_fqdn_returns_correctly_for_atsign(self):
        name = '@'
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        sip = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(sip)
        self.assertEqual(domain.name, dnsresource.fqdn)

    def test_allows_underscores_without_addresses(self):
        name = factory.make_name('n_me')
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource_from_db = DNSResource.objects.get(name=name)
        self.assertThat(dnsresource_from_db, MatchesStructure.byEquality(
            name=name))

    def test_rejects_addresses_if_underscore_in_name(self):
        name = factory.make_name('n_me')
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        sip = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(sip)
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': ['Invalid dnsresource name: %s." % (
                        name,
                    ))):
            dnsresource.save()

    def test_rejects_multiple_dnsresource_with_same_name(self):
        name = factory.make_name('name')
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource2 = DNSResource(name=name, domain=domain)
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': "
                    "['Labels must be unique within their zone.']")):
            dnsresource2.save()

    def test_invalid_name_raises_exception(self):
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': "
                    "['Invalid dnsresource name: invalid*name.']")):
            factory.make_DNSResource(name='invalid*name')

    def test_rejects_address_with_cname(self):
        name = factory.make_name('name')
        domain = factory.make_Domain()
        dnsdata = factory.make_DNSData(
            rrtype='CNAME', name=name, domain=domain)
        ipaddress = factory.make_StaticIPAddress()
        dnsrr = dnsdata.dnsresource
        dnsrr.ip_addresses.add(ipaddress)
        with ExpectedException(
                ValidationError,
                re.escape(
                    "{'__all__': "
                    "['Cannot add address: CNAME present.']")):
            dnsrr.save()

    def test_get_addresses_returns_addresses(self):
        # Verify that the return includes node addresses, and
        # dnsresource-attached addresses.
        name = factory.make_name()
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        subnet = factory.make_Subnet()
        node = factory.make_Node_with_Interface_on_Subnet(
            subnet=subnet, hostname=name, domain=domain)
        sip1 = factory.make_StaticIPAddress()
        node.interface_set.first().ip_addresses.add(sip1)
        sip2 = factory.make_StaticIPAddress()
        dnsresource.ip_addresses.add(sip2)
        self.assertItemsEqual(
            (sip1.get_ip(), sip2.get_ip()),
            dnsresource.get_addresses())
