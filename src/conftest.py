# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from pathlib import Path

import pytest

from provisioningserver.utils.env import MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET, MAAS_SECRET


@pytest.fixture(autouse=True)
def setup_testenv(monkeypatch, tmpdir):
    maas_root = tmpdir.join("maas_root")
    maas_root.mkdir()
    maas_data = tmpdir.join("maas_data")
    maas_data.mkdir()
    monkeypatch.setenv("MAAS_ROOT", str(maas_root))
    monkeypatch.setenv("MAAS_DATA", str(maas_data))
    yield


@pytest.fixture(autouse=True)
def clean_globals(tmpdir):
    base_path = Path(tmpdir)
    for var in (MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET):
        var.clear_cached()
        var._path = lambda: base_path / var.name

    MAAS_SECRET.set(None)
    yield
