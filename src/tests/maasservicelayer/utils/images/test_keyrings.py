# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Tests for the images keyring management functions."""

from base64 import b64encode
import hashlib
import os
from unittest.mock import call, MagicMock, mock_open, patch

from structlog.testing import capture_logs

from maasservicelayer.utils.images import keyrings
from maastesting.factory import factory


class TestWriteKeyring:
    """Tests for `write_keyring().`"""

    def test_writes_keyring_to_file(self) -> None:
        keyring_data = b64encode(b"A keyring! My kingdom for a keyring!")
        keyring_path = os.path.join("/tmp/keyrings", "a-keyring-file")

        expected_data = keyring_data

        with patch(
            "builtins.open", mock_open(read_data=expected_data)
        ) as mock_keyring_file:
            keyrings.write_keyring(keyring_path, keyring_data)

            mock_keyring_file.assert_called_once_with(keyring_path, "wb")
            mock_keyring_file.return_value.__enter__().write.assert_called_once_with(
                expected_data
            )


class TestCalculateKeyringName:
    """Tests for `calculate_keyring_name()`."""

    def test_creates_name_from_url(self) -> None:
        path = "/".join(factory.make_name(size=16) for _ in range(1, 5))
        source_url = f"http://example.com/{path}"

        expected_keyring_name = hashlib.md5(
            source_url.encode("utf8")
        ).hexdigest()
        actual_keyring_name = keyrings.calculate_keyring_name(source_url)

        assert expected_keyring_name == actual_keyring_name


class TestWriteAllKeyrings:
    """Test for the `write_all_keyrings()` function."""

    @patch("maasservicelayer.utils.images.keyrings.write_keyring")
    def test_writes_keyring_data(
        self,
        mock_write_keyring: MagicMock,
    ) -> None:
        sources = [
            {
                "url": factory.make_url(scheme="http"),
                "keyring_data": factory.make_bytes(),
            }
            for _ in range(5)
        ]

        keyring_path = factory.make_absolute_path()

        keyrings.write_all_keyrings(keyring_path, sources)

        expected_calls = list(
            call(
                os.path.join(
                    keyring_path,
                    keyrings.calculate_keyring_name(source["url"]),
                ),
                source["keyring_data"],
            )
            for source in sources
        )
        mock_write_keyring.assert_has_calls(expected_calls)

    @patch("maasservicelayer.utils.images.keyrings.write_keyring")
    def test_returns_sources(
        self,
        mock_write_keyring: MagicMock,
    ) -> None:
        sources = [
            {
                "url": factory.make_url(scheme="http"),
                "keyring_data": factory.make_bytes(),
            }
            for _ in range(5)
        ]

        keyring_path = factory.make_absolute_path()

        expected_values = [
            os.path.join(
                keyring_path, keyrings.calculate_keyring_name(source["url"])
            )
            for source in sources
        ]

        returned_sources = keyrings.write_all_keyrings(keyring_path, sources)
        actual_values = [source.get("keyring") for source in returned_sources]

        assert mock_write_keyring.call_count == 5
        assert expected_values == actual_values

    @patch("maasservicelayer.utils.images.keyrings.write_keyring")
    def test_ignores_existing_keyrings(
        self,
        mock_write_keyring: MagicMock,
    ) -> None:
        source = {
            "url": factory.make_name(),
            "keyring": factory.make_name(),
            "keyring_data": factory.make_name(),
        }

        keyring_path = factory.make_absolute_path()

        expected_keyring = os.path.join(
            keyring_path, keyrings.calculate_keyring_name(source["url"])
        )

        with capture_logs() as captured_logs:
            [returned_source] = keyrings.write_all_keyrings(
                keyring_path, [source]
            )

            assert expected_keyring == returned_source.get("keyring")
            mock_write_keyring.assert_called_once()

            assert captured_logs[0]["log_level"] == "warning"
            assert (
                captured_logs[0]["event"]
                == "Both a keyring file and keyring data were specified; ignoring the keyring file."
            )
