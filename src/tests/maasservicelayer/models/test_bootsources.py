# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maasservicelayer.models.bootsources import BootSource


class TestBootSource:
    @pytest.mark.parametrize(
        "url, expected_base_url",
        [
            ("http://example.com/", "http://example.com/"),
            (
                "http://example.com/streams/v1/index.json",
                "http://example.com/",
            ),
        ],
    )
    def test_get_base_url(self, url: str, expected_base_url: str):
        bs = BootSource(
            id=0, priority=0, url=url, skip_keyring_verification=False
        )
        assert bs.get_base_url() == expected_base_url
