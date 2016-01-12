# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Domain forms."""

__all__ = []

from maasserver.forms_domain import DomainForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestDomainForm(MAASServerTestCase):

    def test__creates_domain(self):
        domain_name = factory.make_name("domain")
        domain_authoritative = factory.pick_bool()
        form = DomainForm({
            "name": domain_name,
            "authoritative": domain_authoritative,
        })
        self.assertTrue(form.is_valid(), form.errors)
        domain = form.save()
        self.assertEqual(domain_name, domain.name)
        self.assertEqual(domain_authoritative, domain.authoritative)

    def test__doest_require_name_on_update(self):
        domain = factory.make_Domain()
        form = DomainForm(instance=domain, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_domain(self):
        new_name = factory.make_name("domain")
        old_authoritative = factory.pick_bool()
        domain = factory.make_Domain(authoritative=old_authoritative)
        new_authoritative = not old_authoritative
        form = DomainForm(instance=domain, data={
            "name": new_name,
            "authoritative": new_authoritative,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(domain).name)
        self.assertEqual(
            new_authoritative, reload_object(domain).authoritative)
