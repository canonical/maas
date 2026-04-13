# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from os import getenv
from pathlib import Path


def get_maas_data_path(path: str) -> str:
    """Return a path under the MAAS data path."""
    base_path = Path(getenv("MAAS_DATA", "/var/lib/maas"))
    return str(base_path / path)
