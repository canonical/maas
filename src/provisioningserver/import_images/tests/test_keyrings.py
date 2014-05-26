# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for the import_images keyring management functions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from base64 import b64encode
import os

from maastesting.matchers import (
    MockCalledWith,
    MockCallsMatch,
    )
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver.import_images import keyrings
from testtools.matchers import FileContains


class TestWriteKeyring(MAASTestCase):
    """Tests for `write_keyring().`"""

    def test_writes_keyring_to_file(self):
        keyring_data = b"A keyring! My kingdom for a keyring!"
        keyring_path = os.path.join(self.make_dir(), "a-keyring-file")
        keyrings.write_keyring(
            keyring_path, b64encode(keyring_data))
        self.assertTrue(os.path.exists(keyring_path))
        self.assertThat(keyring_path, FileContains(keyring_data))


class TestCalculateKeyringName(MAASTestCase):
    """Tests for `calculate_keyring_name()`."""

    def test_creates_name_from_url(self):
        parts = [self.getUniqueString() for i in range(1, 5)]
        source_url = "http://example.com/%s/" % "/".join(parts)
        expected_keyring_name = "example.com-%s.gpg" % "-".join(parts)
        self.assertEqual(
            expected_keyring_name,
            keyrings.calculate_keyring_name(source_url))


class TestWriteAllKeyrings(MAASTestCase):
    """Test for the `write_all_keyrings()` function."""

    def test_writes_keyring_data(self):
        fake_write_keyring = self.patch(keyrings, 'write_keyring')

        sources = [{
            'url': "http://%s" % self.getUniqueString(),
            'keyring_data': b64encode(self.getUniqueString()),
            } for i in range(5)]

        keyring_path = self.make_dir()
        self.patch(
            keyrings.tempfile,
            'mkdtemp').return_value = keyring_path

        keyrings.write_all_keyrings(sources)

        expected_calls = (
            mock.call(
                os.path.join(
                    keyring_path,
                    keyrings.calculate_keyring_name(source['url'])),
                source['keyring_data'])
            for source in sources)
        self.assertThat(fake_write_keyring, MockCallsMatch(*expected_calls))

    def test_returns_sources(self):
        self.patch(keyrings, 'write_keyring')
        sources = [{
            'url': "http://%s" % self.getUniqueString(),
            'keyring_data': b64encode(self.getUniqueString()),
            } for i in range(5)]

        keyring_path = self.make_dir()
        self.patch(
            keyrings.tempfile,
            'mkdtemp').return_value = keyring_path

        expected_values = [
            os.path.join(
                keyring_path,
                keyrings.calculate_keyring_name(source['url']))
            for source in sources]

        returned_sources = keyrings.write_all_keyrings(sources)
        actual_values = [
            source.get('keyring') for source in returned_sources]
        self.assertEqual(expected_values, actual_values)

    def test_ignores_existing_keyrings(self):
        self.patch(keyrings, 'write_keyring')
        fake_logger = self.patch(keyrings, 'logger')
        source = {
            'url': self.getUniqueString(),
            'keyring': self.getUniqueString(),
            'keyring_data': self.getUniqueString(),
            }

        keyring_path = self.make_dir()
        self.patch(
            keyrings.tempfile,
            'mkdtemp').return_value = keyring_path

        [returned_source] = keyrings.write_all_keyrings([source])
        expected_keyring = os.path.join(
            keyring_path, keyrings.calculate_keyring_name(source['url']))
        self.assertEqual(expected_keyring, returned_source.get('keyring'))
        self.assertThat(
            fake_logger.warning,
            MockCalledWith(
                "Both a keyring file and keyring data were specified; "
                "ignoring the keyring file."))
