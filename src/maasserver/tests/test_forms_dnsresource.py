# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DNSResource forms."""

__all__ = []

from maasserver.forms_dnsresource import DNSResourceForm
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestDNSResourceForm(MAASServerTestCase):

    def test__creates_dnsresource(self):
        name = factory.make_name("dnsresource")
        sip = factory.make_StaticIPAddress()
        domain = factory.make_Domain()
        form = DNSResourceForm({
            "name": name,
            "domain": domain.id,
            "ip_addresses": [sip.id],
        })
        self.assertTrue(form.is_valid(), form.errors)
        dnsresource = form.save()
        self.assertEqual(name, dnsresource.name)
        self.assertEqual(domain.id, dnsresource.domain.id)
        self.assertEqual(sip.id, dnsresource.ip_addresses.first().id)

    def test__doesnt_require_name_on_update(self):
        dnsresource = factory.make_DNSResource()
        form = DNSResourceForm(instance=dnsresource, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test__updates_dnsresource(self):
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("new")
        new_sip_ids = [factory.make_StaticIPAddress().id]
        form = DNSResourceForm(instance=dnsresource, data={
            "name": new_name,
            "ip_addresses": new_sip_ids,
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(dnsresource).name)
        self.assertItemsEqual(
            new_sip_ids, [
                ip.id for ip in
                reload_object(dnsresource).ip_addresses.all()])

    def test__update_allows_multiple_ips(self):
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("new")
        new_sip_ids = [
            factory.make_StaticIPAddress().id for _ in range(3)]
        form = DNSResourceForm(instance=dnsresource, data={
            "name": new_name,
            "ip_addresses": " ".join(str(id) for id in new_sip_ids),
        })
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertEqual(new_name, reload_object(dnsresource).name)
        self.assertItemsEqual(
            new_sip_ids, [
                ip.id for ip in
                reload_object(dnsresource).ip_addresses.all()])
