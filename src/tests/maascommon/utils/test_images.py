# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest

from maascommon.utils.images import (
    format_ubuntu_distro_series,
    get_distro_series_info_row,
)


@pytest.mark.parametrize("series", ["plucky", "noble", "jammy", "focal"])
def test_get_distro_series_info_row(series: str) -> None:
    res = get_distro_series_info_row(series)
    assert res is not None


@pytest.mark.parametrize("series", ["", "test", "foo"])
def test_get_distro_series_info_row_non_existent(series: str) -> None:
    res = get_distro_series_info_row(series)
    assert res is None


@pytest.mark.parametrize(
    "series,expected",
    [
        ("plucky", "25.04"),
        ("noble", "24.04 LTS"),
        ("jammy", "22.04 LTS"),
        ("focal", "20.04 LTS"),
        ("nonexistent", "nonexistent"),
    ],
)
def test_format_ubuntu_distro_series(series: str, expected: str) -> None:
    res = format_ubuntu_distro_series(series)
    assert res == expected
