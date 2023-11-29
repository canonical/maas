# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Domain API."""


import http.client
import json
import random

from django.conf import settings
from django.urls import reverse

from maasserver.models import GlobalDefault
from maasserver.models.dnspublication import zone_serial
from maasserver.models.domain import Domain
from maasserver.sequence import INT_MAX
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object


def get_domains_uri():
    """Return a Domain's URI on the API."""
    return reverse("domains_handler", args=[])


def get_domain_uri(domain):
    """Return a Domain URI on the API."""
    return reverse("domain_handler", args=[domain.id])


class TestDomainsAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/domains/", get_domains_uri())

    def test_read(self):
        for _ in range(3):
            factory.make_Domain()
        uri = get_domains_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [domain.id for domain in Domain.objects.all()]
        result_ids = [domain["id"] for domain in response.json()]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        domain_name = factory.make_name("domain")
        uri = get_domains_uri()
        response = self.client.post(uri, {"name": domain_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            domain_name,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "name"
            ],
        )

    def test_create_admin_only(self):
        domain_name = factory.make_name("domain")
        uri = get_domains_uri()
        response = self.client.post(uri, {"name": domain_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_name(self):
        self.become_admin()
        uri = get_domains_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_can_set_serial(self):
        zone_serial.create_if_not_exists()
        self.become_admin()
        uri = get_domains_uri()
        serial = random.randint(1, INT_MAX)
        response = self.client.post(
            uri, {"op": "set_serial", "serial": str(serial)}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        # The handler forces a DNS reload by creating a new DNS publication,
        # so the serial has already been incremented.
        self.assertEqual(serial + 1, next(zone_serial))

    def test_set_serial_rejects_serials_less_than_1(self):
        zone_serial.create_if_not_exists()
        self.become_admin()
        uri = get_domains_uri()
        # A serial of 1 is fine.
        response = self.client.post(uri, {"op": "set_serial", "serial": "1"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        # A serial of 0 is rejected.
        response = self.client.post(uri, {"op": "set_serial", "serial": "0"})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )

    def test_set_serial_rejects_serials_greater_than_4294967295(self):
        zone_serial.create_if_not_exists()
        self.become_admin()
        uri = get_domains_uri()
        # A serial of 4294967295 is fine.
        response = self.client.post(
            uri, {"op": "set_serial", "serial": "4294967295"}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        # A serial of 4294967296 is rejected.
        response = self.client.post(
            uri, {"op": "set_serial", "serial": "4294967296"}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestDomainAPI(APITestCase.ForUser):
    def test_handler_path(self):
        domain = factory.make_Domain()
        self.assertEqual(
            "/MAAS/api/2.0/domains/%s/" % domain.id, get_domain_uri(domain)
        )

    def test_read(self):
        domain = factory.make_Domain()
        for _ in range(3):
            factory.make_DNSData(domain=domain)
        uri = get_domain_uri(domain)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_domain = response.json()
        self.assertEqual(parsed_domain["id"], domain.id)
        self.assertEqual(parsed_domain["name"], domain.get_name())
        self.assertEqual(parsed_domain["resource_record_count"], 3)

    def test_read_includes_default_domain(self):
        defaults = GlobalDefault.objects.instance()
        old_default = Domain.objects.get_default_domain()
        domain = factory.make_Domain()
        defaults.domain = domain
        defaults.save()
        uri = get_domain_uri(domain)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_domain = response.json()
        self.assertTrue(parsed_domain.get("is_default"))
        uri = get_domain_uri(old_default)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_domain = response.json()
        self.assertFalse(parsed_domain.get("is_default"))

    def test_read_404_when_bad_id(self):
        uri = reverse("domain_handler", args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        authoritative = factory.pick_bool()
        domain = factory.make_Domain(authoritative=authoritative)
        new_name = factory.make_name("domain")
        new_ttl = random.randint(10, 1000)
        new_auth = not authoritative
        uri = get_domain_uri(domain)
        response = self.client.put(
            uri, {"name": new_name, "authoritative": new_auth, "ttl": new_ttl}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        ret = json.loads(response.content.decode(settings.DEFAULT_CHARSET))
        domain = reload_object(domain)
        self.assertEqual(new_name, ret["name"])
        self.assertEqual(new_name, domain.name)
        self.assertEqual(new_ttl, ret["ttl"])
        self.assertEqual(new_ttl, domain.ttl)
        self.assertEqual(new_auth, ret["authoritative"])
        self.assertEqual(new_auth, domain.authoritative)

    def test_update_admin_only(self):
        domain = factory.make_Domain()
        new_name = factory.make_name("domain")
        uri = get_domain_uri(domain)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_set_default(self):
        self.become_admin()
        domain = factory.make_Domain()
        self.assertFalse(domain.is_default())
        uri = get_domain_uri(domain)
        response = self.client.post(uri, {"op": "set_default"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        ret = response.json()
        domain = reload_object(domain)
        self.assertTrue(ret["is_default"])
        self.assertTrue(domain.is_default())

    def test_set_default_admin_only(self):
        domain = factory.make_Domain()
        uri = get_domain_uri(domain)
        self.client.post(uri, {"op": "set_default"})

    def test_delete_deletes_domain(self):
        self.become_admin()
        domain = factory.make_Domain()
        uri = get_domain_uri(domain)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(domain))

    def test_delete_403_when_not_admin(self):
        domain = factory.make_Domain()
        uri = get_domain_uri(domain)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(domain))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("domain_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
