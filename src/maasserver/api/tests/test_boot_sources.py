# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Boot Sources` API."""

import http.client

from django.urls import reverse

from maasserver.api.boot_sources import DISPLAYED_BOOTSOURCE_FIELDS
from maasserver.models import BootSource
from maasserver.models.signals import bootsources
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from maastesting.utils import sample_binary_data


def get_boot_source_uri(boot_source):
    """Return a boot source's URI on the API."""
    return reverse("boot_source_handler", args=[boot_source.id])


class TestBootSourceAPI(APITestCase.ForUser):
    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/boot-sources/3/",
            reverse("boot_source_handler", args=["3"]),
        )

    def test_GET_returns_boot_source(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        response = self.client.get(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.OK, response.status_code)
        returned_boot_source = json_load_bytes(response.content)
        # The returned object contains a 'resource_uri' field.
        self.assertEqual(
            reverse("boot_source_handler", args=[boot_source.id]),
            returned_boot_source["resource_uri"],
        )
        # The other fields are the boot source's fields.
        del returned_boot_source["resource_uri"]
        # JSON loads the keyring_data as a str, but it needs to be bytes.
        returned_boot_source["keyring_data"] = returned_boot_source[
            "keyring_data"
        ].encode("utf-8")
        # All the fields are present.
        self.assertEqual(
            set(DISPLAYED_BOOTSOURCE_FIELDS), returned_boot_source.keys()
        )
        # Remove created and updated that is handled by django.
        del returned_boot_source["created"]
        del returned_boot_source["updated"]

        self.assertGreater(
            vars(boot_source).items(), returned_boot_source.items()
        )
        self.assertNotIn(b"<memory at", returned_boot_source["keyring_data"])

    def test_GET_requires_admin(self):
        boot_source = factory.make_BootSource()
        response = self.client.get(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_DELETE_deletes_boot_source(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        response = self.client.delete(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(boot_source))

    def test_DELETE_requires_admin(self):
        boot_source = factory.make_BootSource()
        response = self.client.delete(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_updates_boot_source(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        new_values = {
            "url": "http://example.com/",
            "keyring_filename": factory.make_name("filename"),
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.url, new_values["url"])
        self.assertEqual(
            boot_source.keyring_filename, new_values["keyring_filename"]
        )

    def test_PUT_requires_admin(self):
        boot_source = factory.make_BootSource()
        new_values = {
            "url": "http://example.com/",
            "keyring_filename": factory.make_name("filename"),
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestBootSourcesAPI(APITestCase.ForUser):
    """Test the the boot source API."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_handler_path(self):
        self.assertEqual(
            "/MAAS/api/2.0/boot-sources/", reverse("boot_sources_handler")
        )

    def test_GET_returns_boot_source_list(self):
        self.become_admin()
        sources = [factory.make_BootSource() for _ in range(3)]
        response = self.client.get(reverse("boot_sources_handler"))
        self.assertEqual(
            http.client.OK, response.status_code, response.content
        )
        parsed_result = json_load_bytes(response.content)
        self.assertCountEqual(
            [boot_source.id for boot_source in sources],
            [boot_source.get("id") for boot_source in parsed_result],
        )

    def test_GET_requires_admin(self):
        response = self.client.get(reverse("boot_sources_handler"))
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_POST_creates_boot_source_with_keyring_filename(self):
        self.become_admin()

        params = {
            "url": "http://example.com/",
            "keyring_filename": factory.make_name("filename"),
            "keyring_data": b"",
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)

        boot_source = BootSource.objects.get(id=parsed_result["id"])
        self.assertEqual(boot_source.keyring_data, b"")
        self.assertEqual(
            boot_source.keyring_filename, params["keyring_filename"]
        )
        self.assertEqual(boot_source.url, params["url"])

    def test_POST_creates_boot_source_with_keyring_data(self):
        self.become_admin()

        params = {
            "url": "http://example.com/",
            "keyring_filename": "",
            "keyring_data": (
                factory.make_file_upload(content=sample_binary_data)
            ),
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)

        boot_source = BootSource.objects.get(id=parsed_result["id"])
        # boot_source.keyring_data is returned as a read-only buffer, test
        # it separately from the rest of the attributes.
        self.assertEqual(sample_binary_data, bytes(boot_source.keyring_data))
        self.assertEqual(
            boot_source.keyring_filename, params["keyring_filename"]
        )
        self.assertEqual(boot_source.url, params["url"])

    def test_POST_validates_boot_source(self):
        self.become_admin()

        params = {"url": "http://example.com/"}
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_requires_admin(self):
        params = {
            "url": "http://example.com/",
            "keyring_filename": "",
            "keyring_data": (
                factory.make_file_upload(content=sample_binary_data)
            ),
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)
