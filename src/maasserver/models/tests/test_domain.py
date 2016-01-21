# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Domain model."""

__all__ = []


import random

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db.models import ProtectedError
from maasserver.enum import NODE_PERMISSION
from maasserver.models.config import Config
from maasserver.models.dnsdata import DNSData
from maasserver.models.domain import (
    DEFAULT_DOMAIN_NAME,
    Domain,
)
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from testtools.matchers import MatchesStructure
from testtools.testcase import ExpectedException


class TestDomainManagerGetDomainOr404(MAASServerTestCase):

    def test__user_view_returns_domain(self):
        user = factory.make_User()
        domain = factory.make_Domain()
        self.assertEqual(
            domain,
            Domain.objects.get_domain_or_404(
                domain.id, user, NODE_PERMISSION.VIEW))

    def test__user_view_returns_domain_by_name(self):
        user = factory.make_User()
        domain = factory.make_Domain()
        self.assertEqual(
            domain,
            Domain.objects.get_domain_or_404(
                'name:%s' % domain.name, user, NODE_PERMISSION.VIEW))

    def test__user_edit_raises_PermissionError(self):
        user = factory.make_User()
        domain = factory.make_Domain()
        self.assertRaises(
            PermissionDenied,
            Domain.objects.get_domain_or_404,
            domain.id, user, NODE_PERMISSION.EDIT)

    def test__user_admin_raises_PermissionError(self):
        user = factory.make_User()
        domain = factory.make_Domain()
        self.assertRaises(
            PermissionDenied,
            Domain.objects.get_domain_or_404,
            domain.id, user, NODE_PERMISSION.ADMIN)

    def test__admin_view_returns_domain(self):
        admin = factory.make_admin()
        domain = factory.make_Domain()
        self.assertEqual(
            domain,
            Domain.objects.get_domain_or_404(
                domain.id, admin, NODE_PERMISSION.VIEW))

    def test__admin_view_returns_domain_by_name(self):
        admin = factory.make_admin()
        domain = factory.make_Domain()
        self.assertEqual(
            domain,
            Domain.objects.get_domain_or_404(
                'name:%s' % domain.name, admin, NODE_PERMISSION.VIEW))

    def test__admin_edit_returns_domain(self):
        admin = factory.make_admin()
        domain = factory.make_Domain()
        self.assertEqual(
            domain,
            Domain.objects.get_domain_or_404(
                domain.id, admin, NODE_PERMISSION.EDIT))

    def test__admin_admin_returns_domain(self):
        admin = factory.make_admin()
        domain = factory.make_Domain()
        self.assertEqual(
            domain,
            Domain.objects.get_domain_or_404(
                domain.id, admin, NODE_PERMISSION.ADMIN))


class TestDomainManager(MAASServerTestCase):

    def test__default_specifier_matches_id(self):
        factory.make_Domain()
        domain = factory.make_Domain()
        factory.make_Domain()
        id = domain.id
        self.assertItemsEqual(
            Domain.objects.filter_by_specifiers('%s' % id),
            [domain]
        )

    def test__default_specifier_matches_name(self):
        factory.make_Domain()
        name = factory.make_name('domain-')
        domain = factory.make_Domain(name=name)
        factory.make_Domain()
        self.assertItemsEqual(
            Domain.objects.filter_by_specifiers(name),
            [domain]
        )

    def test__name_specifier_matches_name(self):
        factory.make_Domain()
        name = factory.make_name('domain-')
        domain = factory.make_Domain(name=name)
        factory.make_Domain()
        self.assertItemsEqual(
            Domain.objects.filter_by_specifiers('name:%s' % name),
            [domain]
        )


class DomainTest(MAASServerTestCase):

    def test_creates_domain(self):
        name = factory.make_name('name')
        domain = Domain(name=name)
        domain.save()
        domain_from_db = Domain.objects.get(name=name)
        self.assertThat(domain_from_db, MatchesStructure.byEquality(
            name=name))

    def test_create_strips_trailing_dot(self):
        name = factory.make_name('name')
        domain = Domain(name=name + ".")
        domain.save()
        domain_from_db = Domain.objects.get(name=name)
        self.assertThat(domain_from_db, MatchesStructure.byEquality(
            name=name))

    def test_get_default_domain_creates_default_domain(self):
        default_domain = Domain.objects.get_default_domain()
        self.assertEqual(0, default_domain.id)
        self.assertEqual(DEFAULT_DOMAIN_NAME, default_domain.get_name())

    def test_invalid_name_raises_exception(self):
        self.assertRaises(
            ValidationError,
            factory.make_Domain,
            name='invalid*name')

    def test_get_default_domain_is_idempotent(self):
        default_domain = Domain.objects.get_default_domain()
        default_domain2 = Domain.objects.get_default_domain()
        self.assertEqual(default_domain.id, default_domain2.id)

    def test_is_default_detects_default_domain(self):
        default_domain = Domain.objects.get_default_domain()
        self.assertTrue(default_domain.is_default())

    def test_is_default_detects_non_default_domain(self):
        name = factory.make_name('name')
        domain = factory.make_Domain(name=name)
        self.assertFalse(domain.is_default())

    def test_can_be_deleted_if_does_not_contain_resources(self):
        name = factory.make_name('name')
        domain = factory.make_Domain(name=name)
        domain.delete()
        self.assertItemsEqual([], Domain.objects.filter(name=name))

    def test_cant_be_deleted_if_contains_resources(self):
        domain = factory.make_Domain()
        factory.make_DNSResource(domain=domain)
        with ExpectedException(ProtectedError):
            domain.delete()

    def test_update_kms_srv_deletes_srv_records(self):
        domain = factory.make_Domain()
        target = "%s.%s" % (factory.make_name(), factory.make_name())
        factory.make_DNSData(
            domain=domain, name='_vlmcs._tcp', resource_type='SRV',
            resource_data='0 0 1688 %s.' % target)
        domain.update_kms_srv('')
        # We would restrict it more, but we just deleted it...
        rrset = DNSData.objects.filter(resource_type='SRV')
        self.assertEqual(0, rrset.count())

    def test_update_kms_srv_creates_srv_records(self):
        domain = factory.make_Domain()
        target = "%s.%s" % (factory.make_name(), factory.make_name())
        domain.update_kms_srv(target)
        srvrr = DNSData.objects.get(
            resource_type='SRV', dnsresource__name="_vlmcs._tcp",
            dnsresource__domain_id=domain.id)
        self.assertEqual("0 0 1688 %s." % target, srvrr.resource_data)

    def test_update_kms_srv_creates_srv_records_on_all_domains(self):
        domains = [factory.make_Domain() for _ in range(random.randint(1, 10))]
        target = "%s.%s" % (factory.make_name(), factory.make_name())
        Config.objects.set_config('windows_kms_host', target)
        for domain in domains:
            srvrr = DNSData.objects.get(
                resource_type='SRV', dnsresource__name="_vlmcs._tcp",
                dnsresource__domain_id=domain.id)
            self.assertEqual("0 0 1688 %s." % target, srvrr.resource_data)
