# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for DNSResource API."""

import http.client
import json
import random

from django.conf import settings
from django.urls import reverse

from maasserver.api.dnsresources import get_dnsresource_queryset
from maasserver.enum import NODE_STATUS
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import Domain
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object


def get_dnsresources_uri():
    """Return a DNSResource's URI on the API."""
    return reverse("dnsresources_handler", args=[])


def get_dnsresource_uri(dnsresource):
    """Return a DNSResource URI on the API."""
    return reverse("dnsresource_handler", args=[dnsresource.id])


class TestDNSResourcesAPI(APITestCase.ForUser):
    def test_handler_path(self):
        self.assertEqual("/MAAS/api/2.0/dnsresources/", get_dnsresources_uri())

    def test_read(self):
        for _ in range(3):
            factory.make_DNSResource()
        uri = get_dnsresources_uri()
        response = self.client.get(uri)

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [
            dnsresource.id for dnsresource in DNSResource.objects.all()
        ]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_all(self):
        self.become_admin()
        for _ in range(3):
            factory.make_DNSResource()
        factory.make_RegionRackController()
        uri = get_dnsresources_uri()
        response = self.client.get(uri, {"all": "true"})

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [
            dnsresource.id
            for dnsresource in get_dnsresource_queryset(all_records=True)
        ]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_with_domain(self):
        for _ in range(3):
            factory.make_DNSResource()
        dnsrr = DNSResource.objects.first()
        uri = get_dnsresources_uri()
        response = self.client.get(uri, {"domain": [dnsrr.domain.name]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [dnsrr.id]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertEqual(expected_ids, result_ids)

    def test_read_all_with_domain(self):
        self.become_admin()
        for _ in range(3):
            factory.make_DNSResource()
        dnsrr = DNSResource.objects.first()
        uri = get_dnsresources_uri()
        response = self.client.get(
            uri, {"all": "true", "domain": [dnsrr.domain.name]}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [-1, dnsrr.id]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_read_all_with_only_implicit_records(self):
        self.become_admin()
        domain = Domain.objects.get_default_domain()
        uri = get_dnsresources_uri()
        machine = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYED, domain=domain
        )
        factory.make_StaticIPAddress(interface=machine.boot_interface)
        response = self.client.get(uri, {"all": "true"})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [-1]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertEqual(expected_ids, result_ids)

    def test_read_with_name(self):
        for _ in range(3):
            factory.make_DNSResource()
        dnsrr = DNSResource.objects.first()
        uri = get_dnsresources_uri()
        response = self.client.get(uri, {"name": [dnsrr.name]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [dnsrr.id]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertEqual(expected_ids, result_ids)

    def test_read_with_type(self):
        for _ in range(10):
            factory.make_DNSData()
        rrtype = DNSData.objects.first().rrtype
        uri = get_dnsresources_uri()
        response = self.client.get(uri, {"rrtype": [rrtype]})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [
            dnsrr.id
            for dnsrr in DNSResource.objects.filter(dnsdata__rrtype=rrtype)
        ]
        result_ids = [
            dnsresource["id"]
            for dnsresource in json.loads(
                response.content.decode(settings.DEFAULT_CHARSET)
            )
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create_by_name_domain__id(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        sip = factory.make_StaticIPAddress()
        uri = get_dnsresources_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "domain": domain.id,
                "ip_addresses": str(sip.ip),
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
            sip.ip,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "ip_addresses"
            ][0]["ip"],
        )

    def test_create_by_name_domain__name(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        sip = factory.make_StaticIPAddress()
        uri = get_dnsresources_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "domain": domain.name,
                "ip_addresses": str(sip.ip),
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
            sip.ip,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "ip_addresses"
            ][0]["ip"],
        )

    def test_create_by_fqdn(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        sip = factory.make_StaticIPAddress()
        uri = get_dnsresources_uri()
        response = self.client.post(
            uri, {"fqdn": fqdn, "ip_addresses": str(sip.ip)}
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
            sip.ip,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "ip_addresses"
            ][0]["ip"],
        )

    def test_create_multiple_ips(self):
        self.become_admin()
        dnsresource_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{dnsresource_name}.{domain.name}"
        ips = [factory.make_StaticIPAddress() for _ in range(2)]
        uri = get_dnsresources_uri()
        response = self.client.post(
            uri,
            {
                "name": dnsresource_name,
                "domain": domain.id,
                "ip_addresses": " ".join([str(ip.ip) for ip in ips]),
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
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
            "ip_addresses"
        ]
        self.assertEqual([ip.ip for ip in ips], [ip["ip"] for ip in result])

    def test_create_admin_only(self):
        dnsresource_name = factory.make_name("dnsresource")
        uri = get_dnsresources_uri()
        response = self.client.post(uri, {"name": dnsresource_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_create_requires_name(self):
        self.become_admin()
        uri = get_dnsresources_uri()
        response = self.client.post(uri, {})
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )


class TestDNSResourceAPI(APITestCase.ForUser):
    def test_handler_path(self):
        dnsresource = factory.make_DNSResource()
        self.assertEqual(
            "/MAAS/api/2.0/dnsresources/%s/" % dnsresource.id,
            get_dnsresource_uri(dnsresource),
        )

    def test_read(self):
        dnsrr = factory.make_DNSResource()
        for _ in range(3):
            factory.make_DNSResource()
        uri = get_dnsresource_uri(dnsrr)
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_dnsresource = json.loads(
            response.content.decode(settings.DEFAULT_CHARSET)
        )
        self.assertEqual(parsed_dnsresource.get("id"), dnsrr.id)
        self.assertEqual(parsed_dnsresource.get("fqdn"), dnsrr.fqdn)

    def test_read_404_when_bad_id(self):
        uri = reverse("dnsresource_handler", args=[random.randint(100, 1000)])
        response = self.client.get(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("dnsresource")
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        self.assertEqual(
            f"{new_name}.{dnsresource.domain.name}",
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "fqdn"
            ],
        )
        self.assertEqual(new_name, reload_object(dnsresource).name)

    def test_update_admin_only(self):
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("dnsresource")
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.put(uri, {"name": new_name})
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_update_by_name_domain__id(self):
        self.become_admin()
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{new_name}.{domain.name}"
        sip = factory.make_StaticIPAddress()
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.put(
            uri,
            {
                "name": new_name,
                "domain": domain.id,
                "ip_addresses": str(sip.ip),
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
            sip.ip,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "ip_addresses"
            ][0]["ip"],
        )

    def test_update_by_name_domain__name(self):
        self.become_admin()
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{new_name}.{domain.name}"
        sip = factory.make_StaticIPAddress()
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.put(
            uri,
            {
                "name": new_name,
                "domain": domain.name,
                "ip_addresses": str(sip.ip),
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
            sip.ip,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "ip_addresses"
            ][0]["ip"],
        )

    def test_update_by_fqdn(self):
        self.become_admin()
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{new_name}.{domain.name}"
        sip = factory.make_StaticIPAddress()
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.put(
            uri, {"fqdn": fqdn, "ip_addresses": str(sip.ip)}
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
            sip.ip,
            json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
                "ip_addresses"
            ][0]["ip"],
        )

    def test_update_multiple_ips(self):
        self.become_admin()
        dnsresource = factory.make_DNSResource()
        new_name = factory.make_name("dnsresource")
        domain = factory.make_Domain()
        fqdn = f"{new_name}.{domain.name}"
        ips = [factory.make_StaticIPAddress() for _ in range(2)]
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.put(
            uri,
            {
                "name": new_name,
                "domain": domain.id,
                "ip_addresses": " ".join([str(ip.ip) for ip in ips]),
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
        result = json.loads(response.content.decode(settings.DEFAULT_CHARSET))[
            "ip_addresses"
        ]
        self.assertEqual([ip.ip for ip in ips], [ip["ip"] for ip in result])

    def test_delete_deletes_dnsresource(self):
        self.become_admin()
        dnsresource = factory.make_DNSResource()
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(dnsresource))

    def test_delete_403_when_not_admin(self):
        dnsresource = factory.make_DNSResource()
        uri = get_dnsresource_uri(dnsresource)
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(dnsresource))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        uri = reverse("dnsresource_handler", args=[random.randint(100, 1000)])
        response = self.client.delete(uri)
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )
