# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path

import pytest

from provisioningserver.utils.env import MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET


@pytest.fixture(autouse=True)
def clean_cached_globals(tmpdir):
    base_path = Path(tmpdir)
    for var in (MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET):
        var.clear_cached()
        var.path = base_path / var.name
    yield
