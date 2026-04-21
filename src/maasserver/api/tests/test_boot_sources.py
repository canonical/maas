# Copyright 2014-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Boot Sources` API."""

import http.client

from django.urls import reverse

from maascommon.constants import (
    CANDIDATE_IMAGES_STREAM_URL,
    STABLE_IMAGES_STREAM_URL,
)
import maasserver.api.boot_sources as boot_source_module
from maasserver.api.boot_sources import DISPLAYED_BOOTSOURCE_FIELDS
from maasserver.audit import Event
from maasserver.auth.tests.test_auth import OpenFGAMockMixin
from maasserver.models import BootSource
from maasserver.models.signals import bootsources
from maasserver.testing.api import APITestCase
from maasserver.testing.factory import factory
from maasserver.utils.converters import json_load_bytes
from maasserver.utils.orm import reload_object
from maastesting.utils import sample_binary_data
from provisioningserver.events import EVENT_TYPES


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

    def test_GET_returns_name_priority_enabled(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        response = self.client.get(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.OK, response.status_code)
        result = json_load_bytes(response.content)
        self.assertEqual(result["name"], boot_source.name)
        self.assertEqual(result["priority"], boot_source.priority)
        self.assertEqual(result["enabled"], boot_source.enabled)
        self.assertEqual(
            result["skip_keyring_verification"],
            boot_source.skip_keyring_verification,
        )

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

    def test_DELETE_creates_audit_event(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        response = self.client.delete(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        events = Event.objects.filter(type__name=EVENT_TYPES.BOOT_SOURCE)
        assert len(events) == 1
        assert (
            events[0].description == f"Deleted boot source {boot_source.url}"
        )

    def test_PUT_updates_boot_source(self):
        self.become_admin()
        self.patch(boot_source_module, "post_commit_do")
        boot_source = factory.make_BootSource()
        new_values = {
            "url": "http://example.com",
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

    def test_PUT_calls_workflow_if_url_changed(self):
        self.become_admin()
        mock_post_commit_do = self.patch(boot_source_module, "post_commit_do")
        boot_source = factory.make_BootSource()
        new_values = {
            "url": "http://example.com",
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.url, new_values["url"])
        mock_post_commit_do.assert_called_once()

    def test_PUT_doesnt_call_workflow_if_url_unchanged(self):
        self.become_admin()
        mock_post_commit_do = self.patch(boot_source_module, "post_commit_do")
        boot_source = factory.make_BootSource()
        new_values = {
            "keyring_filename": factory.make_name("filename"),
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertEqual(
            boot_source.keyring_filename, new_values["keyring_filename"]
        )
        mock_post_commit_do.assert_not_called()

    def test_PUT_creates_general_audit_event(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        new_values = {
            "keyring_filename": factory.make_name("filename"),
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        events = Event.objects.filter(type__name=EVENT_TYPES.BOOT_SOURCE)
        assert len(events) == 1
        assert (
            events[0].description == f"Updated boot source {boot_source.url}"
        )

    def test_PUT_creates_url_changed_audit_event(self):
        self.become_admin()
        self.patch(boot_source_module, "post_commit_do")
        boot_source = factory.make_BootSource()
        new_url = "http://new-url.com"
        new_values = {"url": new_url}
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        events = Event.objects.filter(type__name=EVENT_TYPES.BOOT_SOURCE)
        assert len(events) == 1
        assert (
            events[0].description
            == f"Updated boot source url from {boot_source.url} to {new_url}"
        )

    def test_PUT_requires_admin(self):
        boot_source = factory.make_BootSource()
        new_values = {
            "keyring_filename": factory.make_name("filename"),
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.FORBIDDEN, response.status_code)

    def test_PUT_updates_name(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        new_values = {
            "name": "new-name",
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.name, "new-name")

    def test_PUT_updates_enabled(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        self.assertTrue(boot_source.enabled)
        new_values = {
            "enabled": False,
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertFalse(boot_source.enabled)

    def test_PUT_updates_priority(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        new_values = {
            "priority": 42,
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.priority, 42)

    def test_PUT_updates_skip_keyring_verification(self):
        self.become_admin()
        boot_source = factory.make_BootSource()
        self.assertFalse(boot_source.skip_keyring_verification)
        new_values = {
            "skip_keyring_verification": True,
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertTrue(boot_source.skip_keyring_verification)

    def test_PUT_default_boot_source_allows_priority_and_enabled(self):
        self.become_admin()
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        new_values = {"priority": 42, "enabled": False}
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.priority, 42)
        self.assertFalse(boot_source.enabled)

    def test_PUT_default_boot_source_rejects_url(self):
        self.become_admin()
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        new_values = {"url": "http://other.example.com"}
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_PUT_default_boot_source_rejects_name(self):
        self.become_admin()
        boot_source = BootSource.objects.get(url=CANDIDATE_IMAGES_STREAM_URL)
        new_values = {"name": "renamed"}
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_DELETE_rejects_stable_default_boot_source(self):
        self.become_admin()
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        response = self.client.delete(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIsNotNone(reload_object(boot_source))

    def test_DELETE_rejects_candidate_default_boot_source(self):
        self.become_admin()
        boot_source = BootSource.objects.get(url=CANDIDATE_IMAGES_STREAM_URL)
        response = self.client.delete(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)
        self.assertIsNotNone(reload_object(boot_source))


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
        # Stable and candidate are already there from the migration.
        sources = list(BootSource.objects.all())
        sources.extend([factory.make_BootSource() for _ in range(3)])
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
            "url": "http://example.com",
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
            "url": "http://example.com",
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

    def test_POST_creates_audit_event(self):
        self.become_admin()

        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("filename"),
            "keyring_data": b"",
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        events = Event.objects.filter(type__name=EVENT_TYPES.BOOT_SOURCE)
        assert len(events) == 1
        assert events[0].description == f"Created boot source {params['url']}"

    def test_POST_validates_boot_source(self):
        self.become_admin()

        params = {"url": "http://example.com"}
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.BAD_REQUEST, response.status_code)

    def test_POST_creates_boot_source_with_name(self):
        self.become_admin()
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("filename"),
            "name": "custom-source",
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)
        boot_source = BootSource.objects.get(id=parsed_result["id"])
        self.assertEqual(boot_source.name, "custom-source")

    def test_POST_creates_boot_source_with_enabled_false(self):
        self.become_admin()
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("filename"),
            "enabled": False,
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)
        boot_source = BootSource.objects.get(id=parsed_result["id"])
        self.assertFalse(boot_source.enabled)

    def test_POST_creates_boot_source_with_skip_keyring_verification(self):
        self.become_admin()
        params = {
            "url": "http://example.com/",
            "skip_keyring_verification": True,
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        parsed_result = json_load_bytes(response.content)
        boot_source = BootSource.objects.get(id=parsed_result["id"])
        self.assertTrue(boot_source.skip_keyring_verification)

    def test_POST_requires_admin(self):
        params = {
            "url": "http://example.com",
            "keyring_filename": "",
            "keyring_data": (
                factory.make_file_upload(content=sample_binary_data)
            ),
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.FORBIDDEN, response.status_code)


class TestBootSourceOpenFGAIntegration(OpenFGAMockMixin, APITestCase.ForUser):
    def test_GET_requires_can_view_boot_entities(self):
        self.openfga_client.can_view_boot_entities.return_value = True
        factory.make_BootSource()
        response = self.client.get(reverse("boot_sources_handler"))
        self.assertEqual(http.client.OK, response.status_code)
        self.openfga_client.can_view_boot_entities.assert_called_once_with(
            self.user
        )

    def test_PUT_requires_can_view_boot_entities(self):
        self.patch(boot_source_module, "post_commit_do")
        self.openfga_client.can_edit_boot_entities.return_value = True
        boot_source = factory.make_BootSource()
        new_values = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("filename"),
        }
        response = self.client.put(
            get_boot_source_uri(boot_source), new_values
        )
        self.assertEqual(http.client.OK, response.status_code)
        self.openfga_client.can_edit_boot_entities.assert_called_once_with(
            self.user
        )

    def test_DELETE_requires_can_view_boot_entities(self):
        self.openfga_client.can_edit_boot_entities.return_value = True
        boot_source = factory.make_BootSource()
        response = self.client.delete(get_boot_source_uri(boot_source))
        self.assertEqual(http.client.NO_CONTENT, response.status_code)
        self.openfga_client.can_edit_boot_entities.assert_called_once_with(
            self.user
        )


class TestBootSourcesOpenFGAIntegration(OpenFGAMockMixin, APITestCase.ForUser):
    def test_GET_requires_can_view_boot_entities(self):
        self.openfga_client.can_view_boot_entities.return_value = True
        response = self.client.get(reverse("boot_sources_handler"))
        self.assertEqual(http.client.OK, response.status_code)
        self.openfga_client.can_view_boot_entities.assert_called_once_with(
            self.user
        )

    def test_POST_requires_can_edit_boot_entities(self):
        self.openfga_client.can_edit_boot_entities.return_value = True
        params = {
            "url": "http://example.com",
            "keyring_filename": "",
            "keyring_data": (
                factory.make_file_upload(content=sample_binary_data)
            ),
        }
        response = self.client.post(reverse("boot_sources_handler"), params)
        self.assertEqual(http.client.CREATED, response.status_code)
        self.openfga_client.can_edit_boot_entities.assert_called_once_with(
            self.user
        )
