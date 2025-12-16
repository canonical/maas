# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.utils.converters import human_readable_bytes


class TestHumanReadableBytes:
    @pytest.mark.parametrize(
        "size,output,suffix",
        [
            (987, "987", "bytes"),
            (1000 * 35 + 500, "35.5", "kB"),
            ((1000**2) * 28, "28.0", "MB"),
            ((1000**3) * 72, "72.0", "GB"),
            ((1000**4) * 150, "150.0", "TB"),
            (1000**5, "1.0", "PB"),
            (1000**6, "1.0", "EB"),
            (1000**7, "1.0", "ZB"),
            (1000**8, "1.0", "YB"),
        ],
    )
    def test_returns_size_with_suffix(self, size, output, suffix):
        assert human_readable_bytes(size) == f"{output} {suffix}"

    @pytest.mark.parametrize(
        "size,output",
        [
            (987, "987"),
            (1000 * 35 + 500, "35.5"),
            ((1000**2) * 28, "28.0"),
            ((1000**3) * 72, "72.0"),
            ((1000**4) * 150, "150.0"),
            (1000**5, "1.0"),
            (1000**6, "1.0"),
            (1000**7, "1.0"),
            (1000**8, "1.0"),
        ],
    )
    def test_returns_size_without_suffix(self, size, output):
        assert human_readable_bytes(size, include_suffix=False) == output
