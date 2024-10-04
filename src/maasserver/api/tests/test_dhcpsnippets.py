# Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the DHCP snippets API."""


import http.client
import json
import random
from unittest.mock import ANY

from django.urls import reverse

from maasserver.models import DHCPSnippet, Event, VersionedTextFile
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.orm import reload_object
from provisioningserver.events import AUDIT


class TestDHCPSnippetAPI(APITestCase.ForUser):
    """Tests for /api/2.0/dhcp-snippets/<dhcp-snippet>/."""

    @staticmethod
    def get_dhcp_snippet_uri(dhcp_snippet):
        """Return the DHCP snippet's URI on the API."""
        return reverse("dhcp_snippet_handler", args=[dhcp_snippet.id])

    def test_hander_path(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        self.assertEqual(
            "/MAAS/api/2.0/dhcp-snippets/%s/" % dhcp_snippet.id,
            self.get_dhcp_snippet_uri(dhcp_snippet),
        )

    def test_read_by_id(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        # Generate some history
        dhcp_snippet.value = dhcp_snippet.value.update(factory.make_string())
        dhcp_snippet.save()
        response = self.client.get(self.get_dhcp_snippet_uri(dhcp_snippet))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_dhcp_snippet = json.loads(response.content.decode())
        self.assertEqual(
            {
                "id": dhcp_snippet.id,
                "name": dhcp_snippet.name,
                "value": dhcp_snippet.value.data,
                "description": dhcp_snippet.description,
                "history": [
                    {
                        "id": dhcp_snippet.value.id,
                        "value": dhcp_snippet.value.data,
                        "created": ANY,
                    },
                    {
                        "id": dhcp_snippet.value.previous_version.id,
                        "value": dhcp_snippet.value.previous_version.data,
                        "created": ANY,
                    },
                ],
                "enabled": dhcp_snippet.enabled,
                "node": None,
                "subnet": None,
                "global_snippet": True,
                "resource_uri": self.get_dhcp_snippet_uri(dhcp_snippet),
            },
            parsed_dhcp_snippet,
        )

    def test_read_by_name(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        # Generate some history
        dhcp_snippet.value = dhcp_snippet.value.update(factory.make_string())
        dhcp_snippet.save()
        uri = "/MAAS/api/2.0/dhcp-snippets/%s/" % dhcp_snippet.name
        response = self.client.get(uri)
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_dhcp_snippet = json.loads(response.content.decode())
        self.assertEqual(
            {
                "id": dhcp_snippet.id,
                "name": dhcp_snippet.name,
                "value": dhcp_snippet.value.data,
                "description": dhcp_snippet.description,
                "history": [
                    {
                        "id": dhcp_snippet.value.id,
                        "value": dhcp_snippet.value.data,
                        "created": ANY,
                    },
                    {
                        "id": dhcp_snippet.value.previous_version.id,
                        "value": dhcp_snippet.value.previous_version.data,
                        "created": ANY,
                    },
                ],
                "enabled": dhcp_snippet.enabled,
                "node": None,
                "subnet": None,
                "global_snippet": True,
                "resource_uri": self.get_dhcp_snippet_uri(dhcp_snippet),
            },
            parsed_dhcp_snippet,
        )

    def test_read_404_when_bad_id(self):
        response = self.client.get(
            reverse("dhcp_snippet_handler", args=[random.randint(0, 100)])
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_update(self):
        self.become_admin()
        dhcp_snippet = factory.make_DHCPSnippet()
        new_value = factory.make_string()
        response = self.client.put(
            self.get_dhcp_snippet_uri(dhcp_snippet), {"value": new_value}
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        dhcp_snippet = reload_object(dhcp_snippet)
        self.assertEqual(new_value, dhcp_snippet.value.data)

    def test_update_admin_only(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        new_value = factory.make_string()
        response = self.client.put(
            self.get_dhcp_snippet_uri(dhcp_snippet), {"value": new_value}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )

    def test_delete_deletes_dhcp_snippet(self):
        self.become_admin()
        dhcp_snippet = factory.make_DHCPSnippet()
        response = self.client.delete(self.get_dhcp_snippet_uri(dhcp_snippet))
        self.assertEqual(
            http.client.NO_CONTENT, response.status_code, response.content
        )
        self.assertIsNone(reload_object(dhcp_snippet))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description, "Deleted DHCP snippet '%s'." % dhcp_snippet.name
        )

    def test_delete_admin_only(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        response = self.client.delete(self.get_dhcp_snippet_uri(dhcp_snippet))
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertIsNotNone(reload_object(dhcp_snippet))

    def test_delete_404_when_invalid_id(self):
        self.become_admin()
        response = self.client.delete(
            reverse("dhcp_snippet_handler", args=[random.randint(0, 100)])
        )
        self.assertEqual(
            http.client.NOT_FOUND, response.status_code, response.content
        )

    def test_revert(self):
        self.become_admin()
        dhcp_snippet = factory.make_DHCPSnippet()
        textfile_ids = [dhcp_snippet.value.id]
        for _ in range(10):
            dhcp_snippet.value = dhcp_snippet.value.update(
                factory.make_string()
            )
            dhcp_snippet.save()
            textfile_ids.append(dhcp_snippet.value.id)
        revert_to = random.randint(-10, -1)
        reverted_ids = textfile_ids[revert_to:]
        remaining_ids = textfile_ids[:revert_to]
        response = self.client.post(
            self.get_dhcp_snippet_uri(dhcp_snippet),
            {"op": "revert", "to": revert_to},
        )
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_dhcp_snippet = json.loads(response.content.decode())
        self.assertEqual(
            VersionedTextFile.objects.get(id=textfile_ids[revert_to - 1]).data,
            parsed_dhcp_snippet["value"],
        )
        for i in reverted_ids:
            self.assertRaises(
                VersionedTextFile.DoesNotExist,
                VersionedTextFile.objects.get,
                id=i,
            )
        for i in remaining_ids:
            self.assertIsNotNone(VersionedTextFile.objects.get(id=i))
        event = Event.objects.get(type__level=AUDIT)
        self.assertIsNotNone(event)
        self.assertEqual(
            event.description,
            "Reverted DHCP snippet '%s' to revision '%s'."
            % (dhcp_snippet.name, revert_to),
        )

    def test_revert_admin_only(self):
        dhcp_snippet = factory.make_DHCPSnippet()
        for _ in range(10):
            dhcp_snippet.value = dhcp_snippet.value.update(
                factory.make_string()
            )
            dhcp_snippet.save()
        value_id = dhcp_snippet.value.id
        revert_to = random.randint(-10, -1)
        response = self.client.post(
            self.get_dhcp_snippet_uri(dhcp_snippet),
            {"op": "revert", "to": revert_to},
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
        self.assertEqual(value_id, reload_object(dhcp_snippet).value.id)

    def test_revert_requires_to(self):
        self.become_admin()
        dhcp_snippet = factory.make_DHCPSnippet()
        response = self.client.post(
            self.get_dhcp_snippet_uri(dhcp_snippet), {"op": "revert"}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            b"You must specify where to revert to", response.content
        )

    def test_revert_requires_to_to_be_an_int(self):
        self.become_admin()
        dhcp_snippet = factory.make_DHCPSnippet()
        to = factory.make_name("to")
        response = self.client.post(
            self.get_dhcp_snippet_uri(dhcp_snippet), {"op": "revert", "to": to}
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "%s is an invalid 'to' value" % to, response.content.decode()
        )

    def test_revert_errors_on_invalid_id(self):
        self.become_admin()
        dhcp_snippet = factory.make_DHCPSnippet()
        textfile = VersionedTextFile.objects.create(data=factory.make_string())
        response = self.client.post(
            self.get_dhcp_snippet_uri(dhcp_snippet),
            {"op": "revert", "to": textfile.id},
        )
        self.assertEqual(
            http.client.BAD_REQUEST, response.status_code, response.content
        )
        self.assertEqual(
            "%s not found in history" % textfile.id, response.content.decode()
        )


class TestDHCPSnippetsAPI(APITestCase.ForUser):
    """Tests for /api/2.0/dhcp-snippets."""

    @staticmethod
    def get_dhcp_snippets_uri():
        """Return the DHCP snippets URI on the API."""
        return reverse("dhcp_snippets_handler", args=[])

    def test_hander_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/dhcp-snippets/", self.get_dhcp_snippets_uri()
        )

    def test_read(self):
        for _ in range(3):
            factory.make_DHCPSnippet()
        response = self.client.get(self.get_dhcp_snippets_uri())

        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        expected_ids = [
            dhcp_snippet.id for dhcp_snippet in DHCPSnippet.objects.all()
        ]
        result_ids = [
            dhcp_snippet["id"]
            for dhcp_snippet in json.loads(response.content.decode())
        ]
        self.assertCountEqual(expected_ids, result_ids)

    def test_create(self):
        self.become_admin()
        name = factory.make_name("name")
        value = factory.make_string()
        description = factory.make_string()
        enabled = factory.pick_bool()
        response = self.client.post(
            self.get_dhcp_snippets_uri(),
            {
                "name": name,
                "value": value,
                "description": description,
                "enabled": enabled,
            },
        )
        parsed_dhcp_snippet = json.loads(response.content.decode())
        self.assertEqual(name, parsed_dhcp_snippet["name"])
        self.assertEqual(value, parsed_dhcp_snippet["value"])
        self.assertEqual(description, parsed_dhcp_snippet["description"])
        self.assertEqual(enabled, parsed_dhcp_snippet["enabled"])

    def test_create_admin_only(self):
        response = self.client.post(
            self.get_dhcp_snippets_uri(), {"value": factory.make_string()}
        )
        self.assertEqual(
            http.client.FORBIDDEN, response.status_code, response.content
        )
