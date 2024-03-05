# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from django.db import transaction
import hvac
import pytest

from maasserver import vault
from maasserver.config import RegionConfiguration
from maasserver.rbac import FakeRBACClient, rbac
from maasserver.secrets import SecretManager
from maasserver.vault import (
    get_region_vault_client,
    get_region_vault_client_if_enabled,
)


@pytest.fixture(autouse=True)
def clean_globals(clean_globals):
    get_region_vault_client.cache_clear()
    get_region_vault_client_if_enabled.cache_clear()
    yield


@pytest.fixture
def vault_regionconfig(mocker):
    store = {}

    @contextmanager
    def config_ctx():
        yield RegionConfiguration(store)

    mocker.patch.object(vault.RegionConfiguration, "open", config_ctx)
    mocker.patch.object(
        vault.RegionConfiguration, "open_for_update", config_ctx
    )
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

    def delete_metadata_and_all_versions(self, path, mount_point="secret"):
        assert mount_point == self.expected_mount_point
        self.store.pop(path, None)


@pytest.fixture
def mock_hvac_client(mocker):
    """Return an hvac.Client with some mocks, and a dict-based K/V store.

    The mocked store is accessible via the `mock_kv.store` attribute.
    """
    token_expiry = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
    expire_time = token_expiry.isoformat().replace("+00:00", "000Z")

    mock_kv = MockKVStore()
    cli = mocker.patch.object(hvac, "Client").return_value
    cli.auth.token.lookup_self = lambda: {"data": {"expire_time": expire_time}}
    cli.secrets.kv.v2 = mock_kv
    cli.mock_kv = mock_kv
    yield cli


@pytest.fixture
def enable_rbac(maasdb):
    with transaction.atomic():
        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://auth.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
                "rbac-url": "http://rbac.example.com",
            },
        )

    client = FakeRBACClient()
    rbac._store.client = client
    rbac._store.cleared = False
    yield client.store
    rbac._store.client = None
    rbac.clear()
