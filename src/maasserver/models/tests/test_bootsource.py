# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSource`."""

import os
from unittest.mock import Mock

from django.core.exceptions import ValidationError

from maasserver.models.bootsource import BootSource
from maasserver.models.signals import bootsources
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


def make_BootSource():
    """Return a `BootSource` with random keyring data."""
    return factory.make_BootSource(keyring_data=factory.make_bytes())


class TestBootSource(MAASServerTestCase):
    """Tests for the `BootSource` model."""

    def setUp(self):
        super().setUp()
        # Disable boot source cache signals.
        self.addCleanup(bootsources.signals.enable)
        bootsources.signals.disable()

    def test_valid_boot_source_is_valid(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="/path/to/something"
        )
        boot_source.save()
        self.assertTrue(BootSource.objects.filter(id=boot_source.id).exists())

    def test_url_is_unqiue(self):
        boot_source = factory.make_BootSource()
        self.assertRaises(
            ValidationError, factory.make_BootSource, url=boot_source.url
        )

    def test_cannot_set_keyring_data_and_filename(self):
        # A BootSource cannot have both a keyring filename and keyring
        # data. Attempting to set both will raise an error.
        boot_source = BootSource(
            url="http://example.com",
            keyring_filename="/path/to/something",
            keyring_data=b"blahblahblahblah",
        )
        self.assertRaises(ValidationError, boot_source.clean)

    def test_cannot_leave_keyring_data_and_filename_unset(self):
        boot_source = BootSource(
            url="http://example.com", keyring_filename="", keyring_data=b""
        )
        self.assertRaises(ValidationError, boot_source.clean)

    def test_to_dict_returns_dict(self):
        boot_source = factory.make_BootSource(
            keyring_data=b"123445", keyring_filename=""
        )
        boot_source_selection = factory.make_BootSourceSelection(
            boot_source=boot_source
        )
        boot_source_dict = boot_source.to_dict()
        self.assertEqual(boot_source.url, boot_source_dict["url"])
        self.assertEqual(
            [boot_source_selection.to_dict()], boot_source_dict["selections"]
        )

    def test_to_dict_handles_keyring_file(self):
        keyring_data = b"Some Keyring Data"
        keyring_file = self.make_file(contents=keyring_data)
        self.addCleanup(os.remove, keyring_file)

        boot_source = factory.make_BootSource(
            keyring_data=b"", keyring_filename=keyring_file
        )
        source = boot_source.to_dict()
        self.assertEqual(source["keyring_data"], keyring_data)

    def test_to_dict_handles_keyring_data(self):
        keyring_data = b"Some Keyring Data"
        boot_source = factory.make_BootSource(
            keyring_data=keyring_data, keyring_filename=""
        )
        source = boot_source.to_dict()
        self.assertEqual(source["keyring_data"], keyring_data)

    def test_to_dict_with_selections_returns_dict_without_selections(self):
        boot_source = factory.make_BootSource(
            keyring_data=b"123445", keyring_filename=""
        )
        factory.make_BootSourceSelection(boot_source=boot_source)
        boot_source_dict = boot_source.to_dict_without_selections()
        self.assertEqual([], boot_source_dict["selections"])

    def test_to_dict_with_selections_returns_bootloaders(self):
        keyring_data = b"Some Keyring Data"
        boot_source = factory.make_BootSource(
            keyring_data=keyring_data, keyring_filename=""
        )
        boot_source_selection = factory.make_BootSourceSelection(
            boot_source=boot_source
        )
        bootloaders = []
        for arch in boot_source_selection.arches:
            bootloader_type = factory.make_name("bootloader-type")
            factory.make_BootSourceCache(
                boot_source=boot_source,
                bootloader_type=bootloader_type,
                release=bootloader_type,
                arch=arch,
            )
            bootloaders.append(bootloader_type)
        self.assertCountEqual(
            [
                selection["release"]
                for selection in boot_source.to_dict()["selections"]
                if "bootloader-type" in selection["release"]
            ],
            bootloaders,
        )

    def test_compare_dict_without_selections_compares_True_to_self(self):
        boot_source = make_BootSource()
        boot_source_dict = boot_source.to_dict_without_selections()
        self.assertTrue(
            boot_source.compare_dict_without_selections(boot_source_dict)
        )

    def test_compare_dict_without_selections_compares_False_to_other(self):
        boot_source_1 = make_BootSource()
        boot_source_2 = make_BootSource()
        self.assertFalse(
            boot_source_1.compare_dict_without_selections(
                boot_source_2.to_dict_without_selections()
            )
        )

    def test_compare_dict_without_selections_ignores_selections(self):
        boot_source = make_BootSource()
        boot_source_dict = boot_source.to_dict()
        self.assertTrue(
            boot_source.compare_dict_without_selections(boot_source_dict)
        )

    def test_compare_dict_without_selections_ignores_other_keys(self):
        boot_source = make_BootSource()
        boot_source_dict = boot_source.to_dict()
        boot_source_dict[factory.make_name("key")] = factory.make_name("value")
        self.assertTrue(
            boot_source.compare_dict_without_selections(boot_source_dict)
        )

    def test_generate_priority_boot_source(self):
        # create a boot source
        boot_source_1 = make_BootSource()
        assert boot_source_1.priority == 1
        # update boot source: _generate_priority() is called
        boot_source_1.url = "http://%s.com/" % factory.make_name("source-url")
        boot_source_1._generate_priority = Mock(
            return_value=boot_source_1.priority
        )
        boot_source_1.save()
        boot_source_1._generate_priority.assert_called()
        assert boot_source_1.priority == 1
        # create a new boot source (max priority == 1)
        boot_source_2 = make_BootSource()
        assert boot_source_2.priority == 2
        # create a new boot source (max priority == 10)
        boot_source_1._generate_priority.return_value = 10
        boot_source_1.save()
        boot_source_2 = make_BootSource()
        assert boot_source_2.priority == 11

    def test_generate_skip_keyring_verification(self):
        # create a boot source providing a basic URL
        boot_source_1 = make_BootSource()
        assert not boot_source_1.skip_keyring_verification
        # create a boot source using an unsigned json index
        boot_source_2 = factory.make_BootSource(
            url="https://images.maas.io/ephemeral-v3/candidate/streams/v1/index.json"
        )
        assert boot_source_2.skip_keyring_verification
        boot_source_2.skip_keyring_verification = False
        assert not boot_source_2.skip_keyring_verification
        # create a boot source using a signed json index
        boot_source_3 = factory.make_BootSource(
            url="https://images.maas.io/ephemeral-v3/candidate/streams/v1/index.sjson"
        )
        assert not boot_source_3.skip_keyring_verification
