
# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DNSResource model."""

__all__ = []


from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models.dnsresource import DNSResource
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
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
        name = factory.make_name('dnsresource-')
        dnsresource = factory.make_DNSResource(name=name)
        factory.make_DNSResource()
        self.assertItemsEqual(
            DNSResource.objects.filter_by_specifiers(name),
            [dnsresource]
        )

    def test__name_specifier_matches_name(self):
        factory.make_DNSResource()
        name = factory.make_name('dnsresource-')
        dnsresource = factory.make_DNSResource(name=name)
        factory.make_DNSResource()
        self.assertItemsEqual(
            DNSResource.objects.filter_by_specifiers('name:%s' % name),
            [dnsresource]
        )


class DNSResourceTest(MAASServerTestCase):

    def test_creates_dnsresource(self):
        name = factory.make_name('name')
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource_from_db = DNSResource.objects.get(name=name)
        self.assertThat(dnsresource_from_db, MatchesStructure.byEquality(
            name=name))

    def test_rejects_multiple_dnsresource_with_same_name(self):
        name = factory.make_name('name')
        domain = factory.make_Domain()
        dnsresource = DNSResource(name=name, domain=domain)
        dnsresource.save()
        dnsresource2 = DNSResource(name=name, domain=domain)
        self.assertRaises(
            ValidationError,
            dnsresource2.save)

    def test_invalid_name_raises_exception(self):
        self.assertRaises(
            ValidationError,
            factory.make_DNSResource,
            name='invalid*name')
