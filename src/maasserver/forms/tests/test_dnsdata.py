# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DNSData forms."""

import random

from maasserver.forms.dnsdata import DNSDataForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object


class TestDNSDataForm(MAASServerTestCase):
    def test_creates_dnsdata(self):
        name = factory.make_name("dnsdata")
        (rrtype, rrdata) = factory.pick_rrset()
        dnsrr = factory.make_DNSResource(no_ip_addresses=True)
        form = DNSDataForm(
            {
                "name": name,
                "dnsresource": dnsrr.id,
                "rrtype": rrtype,
                "rrdata": rrdata,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        dnsdata = form.save()
        self.assertEqual(dnsrr.id, dnsdata.dnsresource.id)
        self.assertEqual(rrtype, dnsdata.rrtype)
        self.assertEqual(rrdata, dnsdata.rrdata)

    def test_accepts_ttl(self):
        name = factory.make_name("dnsdata")
        (rrtype, rrdata) = factory.pick_rrset()
        dnsrr = factory.make_DNSResource(no_ip_addresses=True)
        ttl = random.randint(1, 10000)
        form = DNSDataForm(
            {
                "name": name,
                "dnsresource": dnsrr.id,
                "ttl": ttl,
                "rrtype": rrtype,
                "rrdata": rrdata,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        dnsdata = form.save()
        self.assertEqual(dnsrr.id, dnsdata.dnsresource.id)
        self.assertEqual(rrtype, dnsdata.rrtype)
        self.assertEqual(rrdata, dnsdata.rrdata)
        self.assertEqual(ttl, dnsdata.ttl)

    def test_accepts_ttl_equal_none(self):
        name = factory.make_name("dnsdata")
        (rrtype, rrdata) = factory.pick_rrset()
        dnsrr = factory.make_DNSResource(no_ip_addresses=True)
        ttl = random.randint(1, 10000)
        form = DNSDataForm(
            {
                "name": name,
                "dnsresource": dnsrr.id,
                "ttl": ttl,
                "rrtype": rrtype,
                "rrdata": rrdata,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        dnsdata = form.save()
        form = DNSDataForm(instance=dnsdata, data={"ttl": None})
        self.assertTrue(form.is_valid(), form.errors)
        dnsdata = form.save()
        self.assertEqual(dnsrr.id, dnsdata.dnsresource.id)
        self.assertEqual(rrtype, dnsdata.rrtype)
        self.assertEqual(rrdata, dnsdata.rrdata)
        self.assertIsNone(dnsdata.ttl)

    def test_doesnt_require_name_on_update(self):
        dnsdata = factory.make_DNSData()
        form = DNSDataForm(instance=dnsdata, data={})
        self.assertTrue(form.is_valid(), form.errors)

    def test_updates_dnsdata(self):
        dnsdata = factory.make_DNSData()
        (rrtype, rrdata) = factory.pick_rrset()
        new_ttl = random.randint(1, 1000)
        form = DNSDataForm(
            instance=dnsdata,
            data={"rrtype": rrtype, "rrdata": rrdata, "ttl": new_ttl},
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        dnsdata = reload_object(dnsdata)
        self.assertEqual(rrtype, dnsdata.rrtype)
        self.assertEqual(rrdata, dnsdata.rrdata)
        self.assertEqual(new_ttl, dnsdata.ttl)
