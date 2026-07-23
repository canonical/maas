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

    # MAAS always runs as a snap, so simulate the snap environment variables
    # required by snap-only code paths (e.g. get_running_version,
    # get_maas_cert_tuple) that would otherwise crash when unset. ``SNAP``
    # (the snap root path) is deliberately left unset: setting it would change
    # path-prefixing behaviour (curtin helpers, nginx static roots, wsman
    # config) and break tests exercising the default paths.
    snap_common = tmpdir.join("snap_common")
    snap_common.mkdir()
    monkeypatch.setenv("SNAP_COMMON", str(snap_common))
    monkeypatch.setenv("SNAP_VERSION", "3.0.0-456-g.deadbeef")
    monkeypatch.setenv("SNAP_REVISION", "1234")

    from provisioningserver.utils import version

    version.get_running_version.cache_clear()

    res_store = maas_data.join("image-storage")
    res_store.mkdir()

    # copy all package files into the run dir
    copytree(dev_root / "run-skel", maas_root, dirs_exist_ok=True)
    copytree(dev_root / "package-files", maas_root, dirs_exist_ok=True)

    yield

    version.get_running_version.cache_clear()


@pytest.fixture(autouse=True)
def clean_globals(tmpdir):
    base_path = Path(tmpdir)
    for var in (MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET):
        var.clear_cached()
        var._path = lambda: base_path / var.name  # noqa: B023

    MAAS_SECRET.set(None)
    yield
