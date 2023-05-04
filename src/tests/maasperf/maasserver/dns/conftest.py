# Copyright 2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from tempfile import mkdtemp

import pytest

from provisioningserver.testing.bindfixture import BINDServer


@pytest.fixture()
def dns_config_path(monkeypatch):
    path = mkdtemp(prefix="maas-dns-config")
    monkeypatch.setenv("MAAS_BIND_CONFIG_DIR", path)
    return path


@pytest.fixture()
def zone_file_config_path(monkeypatch):
    path = mkdtemp(prefix="maas-zonefile-config")
    monkeypatch.setenv("MAAS_ZONE_FILE_CONFIG_DIR", path)
    return path


@pytest.fixture()
def bind_server():
    bind = BINDServer()
    bind.setUp()
    return bind
