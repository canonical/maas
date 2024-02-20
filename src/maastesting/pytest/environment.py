# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import importlib
from pathlib import Path
from shutil import copytree

import pytest

from provisioningserver.utils.env import (
    MAAS_ID,
    MAAS_SECRET,
    MAAS_SHARED_SECRET,
    MAAS_UUID,
)

dev_root = Path(
    Path(importlib.util.find_spec("maastesting").origin).parents[2]
)


@pytest.fixture(autouse=True)
def setup_testenv(monkeypatch, tmpdir):
    maas_root = tmpdir.join("maas_root")
    maas_root.mkdir()
    maas_data = tmpdir.join("maas_data")
    maas_data.mkdir()
    maas_cache = tmpdir.join("maas_cache")
    maas_cache.mkdir()
    monkeypatch.setenv("MAAS_ROOT", str(maas_root))
    monkeypatch.setenv("MAAS_DATA", str(maas_data))
    monkeypatch.setenv("MAAS_CACHE", str(maas_cache))

    res_store = maas_data.join("image-storage")
    res_store.mkdir()

    # copy all package files into the run dir
    copytree(dev_root / "run-skel", maas_root, dirs_exist_ok=True)
    copytree(dev_root / "package-files", maas_root, dirs_exist_ok=True)

    yield


@pytest.fixture(autouse=True)
def clean_globals(tmpdir):
    base_path = Path(tmpdir)
    for var in (MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET):
        var.clear_cached()
        var._path = lambda: base_path / var.name

    MAAS_SECRET.set(None)
    yield
