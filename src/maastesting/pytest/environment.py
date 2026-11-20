# Copyright 2023-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
import importlib
import os
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
    monkeypatch.setenv("SNAP_ARCH", "amd64")

    from provisioningserver.utils import version

    version.get_running_version.cache_clear()

    res_store = maas_data.join("image-storage")
    res_store.mkdir()

    # copy all package files into the run dir
    copytree(dev_root / "run-skel", maas_root, dirs_exist_ok=True)
    copytree(dev_root / "package-files", maas_root, dirs_exist_ok=True)

    yield

    version.get_running_version.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def _rack_legacy_secret():
    """Provision MAAS_SECRET once per worker for the rack-legacy leg.

    Under nose, `rack_script.py` reads the shared secret and installs it
    in `MAAS_SECRET` at process start, so every test sees it regardless
    of order. The 2 certificate tests in `test_clusterservice.py` call
    `fernet_encrypt_psk`, which raises `MissingSharedSecret` when no
    prior test in the worker set it. At high xdist worker counts those
    tests can land in a worker where nothing set it first, making them
    flaky on worker distribution. Set a deterministic secret at session
    start (this mode only) so it's present in every worker; the
    per-test `clean_globals` clear is also skipped in this mode (below),
    so it persists for the whole worker session.
    """
    if os.environ.get("MAAS_PYTEST_NO_CROCHET"):
        MAAS_SECRET.set(b"rack-legacy-test-secret")
    yield


@pytest.fixture(autouse=True)
def clean_globals(tmpdir):
    base_path = Path(tmpdir)
    for var in (MAAS_ID, MAAS_UUID, MAAS_SHARED_SECRET):
        var.clear_cached()
        var._path = lambda: base_path / var.name  # noqa: B023

    # Under nose the in-memory MAAS_SECRET persists across tests in a
    # process (set by an earlier test's side effect). The rack-legacy leg
    # (run with MAAS_PYTEST_NO_CROCHET=1) relies on that
    # persistence: 2 certificate tests in test_clusterservice.py call
    # fernet_encrypt_psk, which needs a secret set by a prior test, and
    # fail with MissingSharedSecret when it's cleared per-test. Skip the
    # clear in that mode; explicit .set(value) calls still take effect.
    if not os.environ.get("MAAS_PYTEST_NO_CROCHET"):
        MAAS_SECRET.set(None)
    yield
