# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import os

import hvac
from pytest import fixture

from maasserver import vault
from maasserver.config import RegionConfiguration
from maasserver.testing.factory import factory as maasserver_factory


@fixture(scope="session")
def factory():
    return maasserver_factory


@fixture(autouse=True)
def setup_testenv(monkeypatch):
    curdir = os.getcwd()
    monkeypatch.setenv("MAAS_ROOT", os.path.join(curdir, ".run"))
    monkeypatch.setenv("MAAS_DATA", os.path.join(curdir, ".run/maas"))
    yield


@fixture
def vault_regionconfig(mocker):
    store = {}

    @contextmanager
    def config_ctx():
        yield RegionConfiguration(store)

    mocker.patch.object(vault.RegionConfiguration, "open", config_ctx)
    yield store


class MockKVStore:

    expected_mount_point = "secret"

    def __init__(self):
        self.store = {}

    def create_or_update_secret(self, path, value, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        self.store[path] = value

    def read_secret(self, path, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        try:
            # include only relevant fields in response
            return {"data": {"data": self.store[path]}}
        except KeyError:
            raise hvac.exceptions.InvalidPath(
                url=f"http://localhost:8200/v1/secret/data/{path}",
                method="get",
            )

    def delete_latest_version_of_secret(self, path, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        self.store.pop(path, None)


@fixture
def mock_vault_kv():
    yield MockKVStore()


@fixture
def mock_hvac_client(mocker, mock_vault_kv):
    token_expiry = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
    expire_time = token_expiry.isoformat().replace("+00:00", "000Z")
    cli = mocker.patch.object(hvac, "Client").return_value
    cli.auth.token.lookup_self = lambda: {"data": {"expire_time": expire_time}}
    cli.secrets.kv.v2 = mock_vault_kv
    yield cli
