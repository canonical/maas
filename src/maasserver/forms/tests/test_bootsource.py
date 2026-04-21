# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceForm`."""

from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile

from maascommon.constants import (
    CANDIDATE_IMAGES_STREAM_URL,
    STABLE_IMAGES_STREAM_URL,
)
from maasserver.forms import BootSourceForm
from maasserver.models import BootSource
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import reload_object
from maastesting.utils import sample_binary_data


class TestBootSourceForm(MAASServerTestCase):
    """Tests for `BootSourceForm`."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_edits_boot_source_object(self):
        boot_source = factory.make_BootSource()
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("keyring_filename"),
        }
        form = BootSourceForm(instance=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.url, "http://example.com")
        self.assertEqual(
            boot_source.keyring_filename, params["keyring_filename"]
        )

    def test_creates_boot_source_object_with_keyring_filename(self):
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("keyring_filename"),
        }
        form = BootSourceForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertEqual(boot_source.url, "http://example.com")
        self.assertEqual(
            boot_source.keyring_filename, params["keyring_filename"]
        )

    def test_creates_boot_source_object_with_keyring_data(self):
        in_mem_file = InMemoryUploadedFile(
            BytesIO(sample_binary_data),
            name=factory.make_name("name"),
            field_name=factory.make_name("field-name"),
            content_type="application/octet-stream",
            size=len(sample_binary_data),
            charset=None,
        )
        params = {"url": "http://example.com"}
        form = BootSourceForm(data=params, files={"keyring_data": in_mem_file})
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertEqual(sample_binary_data, bytes(boot_source.keyring_data))
        self.assertEqual(boot_source.url, "http://example.com")

    def test_creates_boot_source_with_name(self):
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("keyring_filename"),
            "name": "my-custom-source",
        }
        form = BootSourceForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertEqual(boot_source.name, "my-custom-source")

    def test_creates_boot_source_with_priority(self):
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("keyring_filename"),
            "priority": 5,
        }
        form = BootSourceForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        # Candidate and stable boot sources are created with priority 1 and 2 respectively, so the next priority is 3
        self.assertEqual(boot_source.priority, 3)

    def test_creates_boot_source_with_enabled_false(self):
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("keyring_filename"),
            "enabled": False,
        }
        form = BootSourceForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertFalse(boot_source.enabled)

    def test_creates_boot_source_without_optional_fields(self):
        params = {
            "url": "http://example.com",
            "keyring_filename": factory.make_name("keyring_filename"),
        }
        form = BootSourceForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertEqual(boot_source.name, "http://example.com")
        # Candidate and stable boot sources are created with priority 1 and 2 respectively, so the next priority is 3
        self.assertEqual(boot_source.priority, 3)
        self.assertTrue(boot_source.enabled)
        self.assertFalse(boot_source.skip_keyring_verification)

    def test_update_default_boot_source_allows_priority(self):
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        form = BootSourceForm(instance=boot_source, data={"priority": 42})
        self.assertTrue(form.is_valid(), form._errors)

    def test_update_default_boot_source_allows_enabled(self):
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        form = BootSourceForm(instance=boot_source, data={"enabled": False})
        self.assertTrue(form.is_valid(), form._errors)

    def test_update_default_boot_source_rejects_url(self):
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        form = BootSourceForm(
            instance=boot_source,
            data={"url": "http://other.example.com"},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("url", form.errors)

    def test_update_default_boot_source_rejects_name(self):
        boot_source = BootSource.objects.get(url=CANDIDATE_IMAGES_STREAM_URL)
        form = BootSourceForm(
            instance=boot_source,
            data={"name": "new-name"},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_update_default_boot_source_rejects_keyring_filename(self):
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        form = BootSourceForm(
            instance=boot_source,
            data={"keyring_filename": "/new/path"},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("keyring_filename", form.errors)

    def test_update_default_boot_source_rejects_skip_keyring_verification(
        self,
    ):
        boot_source = BootSource.objects.get(url=STABLE_IMAGES_STREAM_URL)
        form = BootSourceForm(
            instance=boot_source,
            data={"skip_keyring_verification": True},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("skip_keyring_verification", form.errors)

    def test_update_non_default_boot_source_allows_any_field(self):
        boot_source = factory.make_BootSource()
        form = BootSourceForm(
            instance=boot_source,
            data={
                "url": "http://other.example.com",
                "name": "new-name",
                "keyring_filename": "/new/path",
            },
        )
        self.assertTrue(form.is_valid(), form._errors)
