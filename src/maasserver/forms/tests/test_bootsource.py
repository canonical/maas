# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceForm`."""

from io import BytesIO

from django.core.files.uploadedfile import InMemoryUploadedFile

from maasserver.forms import BootSourceForm
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
            "url": "http://example.com/",
            "keyring_filename": factory.make_name("keyring_filename"),
        }
        form = BootSourceForm(instance=boot_source, data=params)
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        boot_source = reload_object(boot_source)
        self.assertEqual(boot_source.url, "http://example.com/")
        self.assertEqual(
            boot_source.keyring_filename, params["keyring_filename"]
        )

    def test_creates_boot_source_object_with_keyring_filename(self):
        params = {
            "url": "http://example.com/",
            "keyring_filename": factory.make_name("keyring_filename"),
        }
        form = BootSourceForm(data=params)
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertEqual(boot_source.url, "http://example.com/")
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
        params = {"url": "http://example.com/"}
        form = BootSourceForm(data=params, files={"keyring_data": in_mem_file})
        self.assertTrue(form.is_valid(), form._errors)
        boot_source = form.save()
        self.assertEqual(sample_binary_data, bytes(boot_source.keyring_data))
        self.assertEqual(boot_source.url, "http://example.com/")
