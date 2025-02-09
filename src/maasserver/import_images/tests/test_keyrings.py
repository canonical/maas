# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for the import_images keyring management functions."""

import hashlib
import os
from unittest import mock

from maasserver.import_images import keyrings
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase


class TestWriteKeyring(MAASTestCase):
    """Tests for `write_keyring().`"""

    def test_writes_keyring_to_file(self):
        keyring_data = "A keyring! My kingdom for a keyring!"
        keyring_path = os.path.join(self.make_dir(), "a-keyring-file")
        keyrings.write_keyring(keyring_path, keyring_data.encode("utf-8"))
        self.assertTrue(os.path.exists(keyring_path))
        with open(keyring_path, "rb") as fh:
            contents = fh.read()
        self.assertEqual(contents, keyring_data.encode("utf-8"))


class TestCalculateKeyringName(MAASTestCase):
    """Tests for `calculate_keyring_name()`."""

    def test_creates_name_from_url(self):
        path = "/".join(self.getUniqueString() for _ in range(1, 5))
        source_url = f"http://example.com/{path}"
        expected_keyring_name = hashlib.md5(
            source_url.encode("utf8")
        ).hexdigest()
        self.assertEqual(
            expected_keyring_name, keyrings.calculate_keyring_name(source_url)
        )


class TestWriteAllKeyrings(MAASTestCase):
    """Test for the `write_all_keyrings()` function."""

    def test_writes_keyring_data(self):
        fake_write_keyring = self.patch(keyrings, "write_keyring")

        sources = [
            {
                "url": f"http://{self.getUniqueString()}",
                "keyring_data": factory.make_bytes(),
            }
            for _ in range(5)
        ]

        keyring_path = self.make_dir()

        keyrings.write_all_keyrings(keyring_path, sources)

        expected_calls = (
            mock.call(
                os.path.join(
                    keyring_path,
                    keyrings.calculate_keyring_name(source["url"]),
                ),
                source["keyring_data"],
            )
            for source in sources
        )
        fake_write_keyring.assert_has_calls(expected_calls)

    def test_returns_sources(self):
        self.patch(keyrings, "write_keyring")
        sources = [
            {
                "url": f"http://{self.getUniqueString()}",
                "keyring_data": factory.make_bytes(),
            }
            for _ in range(5)
        ]

        keyring_path = self.make_dir()

        expected_values = [
            os.path.join(
                keyring_path, keyrings.calculate_keyring_name(source["url"])
            )
            for source in sources
        ]

        returned_sources = keyrings.write_all_keyrings(keyring_path, sources)
        actual_values = [source.get("keyring") for source in returned_sources]
        self.assertEqual(expected_values, actual_values)

    def test_ignores_existing_keyrings(self):
        self.patch(keyrings, "write_keyring")
        fake_maaslog = self.patch(keyrings, "maaslog")
        source = {
            "url": self.getUniqueString(),
            "keyring": self.getUniqueString(),
            "keyring_data": self.getUniqueString(),
        }

        keyring_path = self.make_dir()

        [returned_source] = keyrings.write_all_keyrings(keyring_path, [source])
        expected_keyring = os.path.join(
            keyring_path, keyrings.calculate_keyring_name(source["url"])
        )
        self.assertEqual(expected_keyring, returned_source.get("keyring"))
        fake_maaslog.warning.assert_called_with(
            "Both a keyring file and keyring data were specified; ignoring the keyring file."
        )
