# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
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
from maasserver.models import bootsource as bootsource_module
from maasserver.models.bootsource import BootSource
from maasserver.models.testing import UpdateBootSourceCacheDisconnected
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import MockCalledOnceWith
from provisioningserver.utils.twisted import deferToNewThread
from twisted.internet import reactor
from twisted.internet.threads import deferToThread


def make_BootSource():
    """Return a `BootSource` with random keyring data."""
    return factory.make_BootSource(keyring_data=factory.make_bytes())


class TestBootSource(MAASServerTestCase):
    """Tests for the `BootSource` model."""

    def setUp(self):
        super(TestBootSource, self).setUp()
        self.useFixture(UpdateBootSourceCacheDisconnected())

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

    def test_compare_dict_without_selections_compares_True_to_self(self):
        boot_source = make_BootSource()
        boot_source_dict = boot_source.to_dict_without_selections()
        self.assertTrue(
            boot_source.compare_dict_without_selections(boot_source_dict))

    def test_compare_dict_without_selections_compares_False_to_other(self):
        boot_source_1 = make_BootSource()
        boot_source_2 = make_BootSource()
        self.assertFalse(
            boot_source_1.compare_dict_without_selections(
                boot_source_2.to_dict_without_selections()))

    def test_compare_dict_without_selections_ignores_selections(self):
        boot_source = make_BootSource()
        boot_source_dict = boot_source.to_dict()
        self.assertTrue(
            boot_source.compare_dict_without_selections(boot_source_dict))

    def test_compare_dict_without_selections_ignores_other_keys(self):
        boot_source = make_BootSource()
        boot_source_dict = boot_source.to_dict()
        boot_source_dict[factory.make_name("key")] = factory.make_name("value")
        self.assertTrue(
            boot_source.compare_dict_without_selections(boot_source_dict))

    # XXX: GavinPanella 2015-03-03 bug=1376317: This test is fragile, possibly
    # due to isolation issues. Note: this test may not be superfluous.
    @skip("Possible isolation issues")
    def test_calls_cache_boot_sources_on_create(self):
        mock_callLater = self.patch(reactor, 'callLater')
        BootSource.objects.create(
            url="http://test.test/", keyring_data=b"1234")
        self.assertThat(
            mock_callLater,
            MockCalledOnceWith(
                1, deferToThread, cache_boot_sources))


class TestBootSourceSignals(MAASServerTestCase):
    """Tests for the `BootSource` model's signals."""

    def test_arranges_for_later_update_to_boot_sources_post_commit(self):
        post_commit_do = self.patch(bootsource_module, "post_commit_do")
        make_BootSource()
        self.assertThat(post_commit_do, MockCalledOnceWith(
            reactor.callLater, 0, deferToNewThread, cache_boot_sources))
