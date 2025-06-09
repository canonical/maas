# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DNSResourceRecord API."""

import http.client
import json
import random

from django.conf import settings
from django.urls import reverse

from maasserver.models.dnsdata import DNSData
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import post_commit_hooks, reload_object


def get_dnsresourcerecords_uri():
    """Return a DNSResourceRecord's URI on the API."""
    return reverse("dnsresourcerecords_handler", args=[])


def get_dnsresourcerecord_uri(dnsresourcerecord):
    """Return a DNSResourceRecord URI on the API."""
    return reverse("dnsresourcerecord_handler", args=[dnsresourcerecord.id])


class TestDNSResourceRecordsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/dnsresourcerecords/", get_dnsresourcerecords_uri()
        )

    def test_read(self):
        for _ in range(3):
            factory.make_DNSData()
        uri = get_dnsresourcerecords_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [dnsdata.id for dnsdata in DNSData.objects.all()]
        result_ids = [
            dnsrr["id"]
            for dnsrr in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_with_domain(self):
        for _ in range(3):
            dnsdata = factory.make_DNSData()
        uri = get_dnsresourcerecords_uri()
        response = self.client.get(
            uri, {"domain": [dnsdata.dnsresource.domain.name]}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [dnsdata.id]
        result_ids = [
            data["id"]
            for data in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_with_name(self):
        for _ in range(3):
            dnsdata = factory.make_DNSData()
        uri = get_dnsresourcerecords_uri()
        response = self.client.get(uri, {"name": [dnsdata.dnsresource.name]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [dnsdata.id]
        result_ids = [
            data["id"]
            for data in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_with_type(self):
        for _ in range(3):
            dnsdata = factory.make_DNSData()
        rrtype = dnsdata.rrtype
        uri = get_dnsresourcerecords_uri()
        response = self.client.get(uri, {"rrtype": [rrtype]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [
            data.id for data in DNSData.objects.filter(rrtype=rrtype)
        ]
        result_ids = [
            data["id"]
            for data in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create_by_name_domain_id(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "domain": domain.id,
                "rrtype": "TXT",
                "rrdata": "Sample Text.",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            fqdn,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "fqdn"
            ],
        )
        self.assertEqual(
            "TXT",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrtype"
            ],
        )
        self.assertEqual(
            "Sample Text.",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrdata"
            ],
        )

    def test_create_by_name_domain_name(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "domain": domain.name,
                "rrtype": "TXT",
                "rrdata": "Sample Text.",
            },
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            fqdn,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "fqdn"
            ],
        )
        self.assertEqual(
            "TXT",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrtype"
            ],
        )
        self.assertEqual(
            "Sample Text.",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrdata"
            ],
        )

    def test_create_by_fqdn(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri, {"fqdn": fqdn, "rrtype": "TXT", "rrdata": "Sample Text."}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            fqdn,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "fqdn"
            ],
        )
        self.assertEqual(
            "TXT",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrtype"
            ],
        )
        self.assertEqual(
            "Sample Text.",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrdata"
            ],
        )

    def test_create_resource_exists(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        # create a resource with the same details
        factory.make_DNSResource(domain=domain, name=dnsresource_name)
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "domain": domain.name,
                "rrtype": "TXT",
                "rrdata": "Sample Text.",
            },
        )
        payload = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        self.assertEqual(payload["fqdn"], f"{dnsresource_name}.{domain.name}")

    def test_create_fails_with_no_name(self):
        self.become_admin()
        domain = factory.make_Domain()
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri,
            {"domain": domain.name, "rrtype": "TXT", "rrdata": "Sample Text."},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_fails_with_no_domain(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "rrtype": "TXT",
                "rrdata": "Sample Text.",
            },
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_create_admin_only(self):
        dnsresource_name = factory.make_name("dnsresource")
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "rrtype": "TXT",
                "rrdata": "Sample Text.",
            },
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_name(self):
        self.become_admin()
        uri = get_dnsresourcerecords_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestDNSResourceRecordAPI(APITestCase.ForUser):
    def test_handler_path(self):
        dnsdata = factory.make_DNSData()
        self.assertEqual(
            "/MAAS/api/2.0/dnsresourcerecords/%s/" % dnsdata.id,
            get_dnsresourcerecord_uri(dnsdata),
        )

    def test_read(self):
        dnsdata = factory.make_DNSData()
        for _ in range(3):
            factory.make_DNSData()
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_dnsresource = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(parsed_dnsresource.get("id"), dnsdata.id)
        self.assertEqual(parsed_dnsresource.get("fqdn"), dnsdata.fqdn)
        self.assertEqual(parsed_dnsresource.get("rrtype"), dnsdata.rrtype)
        self.assertEqual(parsed_dnsresource.get("rrdata"), dnsdata.rrdata)

    def test_read_404_when_bad_id(self):
        uri = reverse(
            "dnsresourcerecord_handler", args=[random.randint(100, 1000)]
        )
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        dnsdata = factory.make_DNSData(rrtype="TXT", rrdata="1")
        new_data = factory.make_name("data")
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.put(uri, {"rrdata": new_data})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            new_data,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "rrdata"
            ],
        )

    def test_update_admin_only(self):
        dnsdata = factory.make_DNSData()
        new_ttl = random.randint(10, 100)
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.put(uri, {"ttl": new_ttl})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_deletes_dnsresource_record(self):
        self.become_admin()
        dnsdata = factory.make_DNSData()
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(dnsdata))

    def test_delete_deletes_dnsresource_if_no_data(self):
        self.become_admin()
        dnsdata = factory.make_DNSData()
        dnsrr = dnsdata.dnsresource
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(dnsdata))
        self.assertIsNone(reload_object(dnsrr))

    def test_delete_does_not_delete_dnsresource_if_data_present(self):
        self.become_admin()
        dnsdata = factory.make_DNSData()
        dnsrr = dnsdata.dnsresource

        with post_commit_hooks:
            while dnsdata.rrtype == "CNAME":
                dnsdata.delete()
                dnsdata = factory.make_DNSData(dnsresource=dnsrr)
        # Now create a second DNSData record for this DNSRR.
        factory.make_DNSData(rrtype=dnsdata.rrtype, dnsresource=dnsrr)
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(dnsdata))
        self.assertEqual(dnsrr, reload_object(dnsrr))

    def test_delete_403_when_not_admin(self):
        dnsdata = factory.make_DNSData()
        uri = get_dnsresourcerecord_uri(dnsdata)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(dnsdata))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse(
            "dnsresourcerecord_handler", args=[random.randint(100, 1000)]
        )
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
