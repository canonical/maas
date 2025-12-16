#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from pathlib import Path

from distro_info import UbuntuDistroInfo

from maascommon.path import get_maas_data_path


def get_bootresource_store_path() -> Path:
    return Path(get_maas_data_path("image-storage"))


def get_distro_series_info_row(series):
    """Returns the distro series row information from python-distro-info."""
    info = UbuntuDistroInfo()
    for row in info._avail(info._date):
        # LP: #1711191 - distro-info 0.16+ no longer returns dictionaries or
        # lists, and it now returns objects instead. As such, we need to
        # handle both cases for backwards compatibility.
        if not isinstance(row, dict):
            row = row.__dict__
        if row["series"] == series:
            return row
    return None


def format_ubuntu_distro_series(series):
    """Formats the Ubuntu distro series into a version name."""
    row = get_distro_series_info_row(series)
    if row is None:
        return series
    return row["version"]
