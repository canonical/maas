# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os

import pytest

from maasapiserver.v3.listeners.vault import VaultMigrationPostgresListener
from maasservicelayer.services import SecretsServiceFactory


@pytest.fixture(autouse=True)
def prepare():
    # Always reset the SecretsServiceFactory cache
    SecretsServiceFactory.clear()
    yield
    SecretsServiceFactory.clear()


class TestVaultMigrationPostgresListener:
    async def test_application_is_killed_on_notification(self, mocker):
        os_mock = mocker.patch.object(os, "_exit")
        os_mock.return_value = None

        SecretsServiceFactory.IS_VAULT_ENABLED = True
        listener = VaultMigrationPostgresListener()
        listener.handler(None, 0, listener.channel, "")  # type: ignore
        os_mock.assert_called_once_with(0)
