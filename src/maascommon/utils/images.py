#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).
from pathlib import Path

from maascommon.path import get_maas_data_path


def get_bootresource_store_path() -> Path:
    return Path(get_maas_data_path("image-storage"))
