# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSource`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
from unittest import skip

from django.core.exceptions import ValidationError
from maasserver.bootsources import cache_boot_sources
from maasserver.models import BootSource
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from twisted.internet import reactor
from twisted.internet.threads import deferToThread


class TestBootSource(MAASServerTestCase):
    """Tests for the `BootSource` model."""

    def test_valid_boot_source_is_valid(self):
        boot_source = BootSource(
            url="http://example.com",
            keyring_filename="/path/to/something")
        boot_source.save()
        self.assertTrue(
            BootSource.objects.filter(id=boot_source.id).exists())

    def test_url_is_unqiue(self):
        boot_source = factory.make_BootSource()
        self.assertRaises(
            ValidationError, factory.make_BootSource, url=boot_source.url)

    def test_cannot_set_keyring_data_and_filename(self):
        # A BootSource cannot have both a keyring filename and keyring
        # data. Attempting to set both will raise an error.
        boot_source = BootSource(
            url="http://example.com",
            keyring_filename="/path/to/something",
            keyring_data=b"blahblahblahblah")
        self.assertRaises(ValidationError, boot_source.clean)

    def test_cannot_leave_keyring_data_and_filename_unset(self):
        boot_source = BootSource(
            url="http://example.com",
            keyring_filename="", keyring_data=b"")
        self.assertRaises(ValidationError, boot_source.clean)

    def test_to_dict_returns_dict(self):
        boot_source = factory.make_BootSource(
            keyring_data=b"123445", keyring_filename='')
        boot_source_selection = factory.make_BootSourceSelection(
            boot_source=boot_source)
        boot_source_dict = boot_source.to_dict()
        self.assertEqual(boot_source.url, boot_source_dict['url'])
        self.assertEqual(
            [boot_source_selection.to_dict()],
            boot_source_dict['selections'])

    def test_to_dict_handles_keyring_file(self):
        keyring_data = b"Some Keyring Data"
        keyring_file = self.make_file(contents=keyring_data)
        self.addCleanup(os.remove, keyring_file)

        boot_source = factory.make_BootSource(
            keyring_data=b"", keyring_filename=keyring_file)
        source = boot_source.to_dict()
        self.assertEqual(
            source['keyring_data'],
            keyring_data)

    def test_to_dict_handles_keyring_data(self):
        keyring_data = b"Some Keyring Data"
        boot_source = factory.make_BootSource(
            keyring_data=keyring_data, keyring_filename="")
        source = boot_source.to_dict()
        self.assertEqual(
            source['keyring_data'],
            keyring_data)

    def test_to_dict_with_selections_returns_dict_without_selections(self):
        boot_source = factory.make_BootSource(
            keyring_data=b"123445", keyring_filename='')
        factory.make_BootSourceSelection(boot_source=boot_source)
        boot_source_dict = boot_source.to_dict_without_selections()
        self.assertEqual(
            [],
            boot_source_dict['selections'])

    # XXX: GavinPanella 2014-10-28 bug=1376317: This test is fragile, possibly
    # due to isolation issues.
    @skip("Possible isolation issues")
    def test_calls_cache_boot_sources_on_create(self):
        mock_callLater = self.patch(reactor, 'callLater')
        BootSource.objects.create(
            url="http://test.test/", keyring_data=b"1234")
        self.assertThat(
            mock_callLater,
            MockCalledOnceWith(
                1, deferToThread, cache_boot_sources))
