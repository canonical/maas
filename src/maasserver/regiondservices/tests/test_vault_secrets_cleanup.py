# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import call

from django.db import transaction
from hvac.exceptions import VaultError
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from maasserver.models import VaultSecret
from maasserver.regiondservices import vault_secrets_cleanup
from maasserver.regiondservices.vault_secrets_cleanup import (
    VaultSecretsCleanupService,
)
from maasserver.secrets import SecretManager
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.testing.vault import FakeVaultClient
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for

wait_for_reactor = wait_for()


class TestVaultSecretsCleanupService(MAASTransactionServerTestCase):
    def setUp(self):
        super().setUp()
        self.service = VaultSecretsCleanupService(reactor)

    def mock_vault_client(self):
        mock_client = FakeVaultClient()
        self.patch(
            vault_secrets_cleanup, "get_region_vault_client_if_enabled"
        ).return_value = mock_client
        return mock_client

    @wait_for_reactor
    @inlineCallbacks
    def test_no_client_no_op(self):
        mock_clean_secrets = self.patch(self.service, "_clean_secrets")
        yield self.service.startService()
        yield self.service.stopService()
        mock_clean_secrets.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_clean_removed(self):
        vault_client = self.mock_vault_client()

        def setup():
            manager = SecretManager(vault_client=vault_client)
            manager.set_simple_secret("omapi-key", "omapi-secret")
            manager.set_simple_secret("rpc-shared", "rpc-secret")
            manager.set_simple_secret("ipmi-k_g-key", "k_g-secret")
            manager.delete_secret("omapi-key")
            manager.delete_secret("ipmi-k_g-key")

        yield deferToDatabase(setup)

        yield self.service.startService()
        yield self.service.stopService()

        def get_vault_secrets():
            return list(VaultSecret.objects.values_list("path", flat=True))

        vault_secrets = yield deferToDatabase(get_vault_secrets)
        self.assertEqual(
            vault_secrets,
            ["global/rpc-shared"],
        )
        self.assertEqual(
            vault_client.store,
            {"global/rpc-shared": {"secret": "rpc-secret"}},
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_clean_only_successful_removals(self):
        vault_client = self.mock_vault_client()

        self.patch(vault_client, "delete").side_effect = [
            VaultError("fail"),
            None,
        ]

        def setup():
            manager = SecretManager(vault_client=vault_client)
            manager.set_simple_secret("omapi-key", "omapi-secret")
            manager.set_simple_secret("rpc-shared", "rpc-secret")
            manager.delete_secret("omapi-key")
            manager.delete_secret("rpc-shared")

        yield deferToDatabase(setup)

        yield self.service.startService()
        yield self.service.stopService()

        def get_vault_secrets():
            return list(VaultSecret.objects.values_list("path", flat=True))

        vault_secrets = yield deferToDatabase(get_vault_secrets)
        self.assertEqual(
            vault_secrets,
            ["global/omapi-key"],
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_clean_deletes_again_if_transaction_fails(self):
        vault_client = self.mock_vault_client()

        mock_delete = self.patch(vault_client, "delete")

        self.patch(self.service, "_delete_secret_entry").side_effect = [
            transaction.TransactionManagementError("Some error"),
            None,
        ]

        def setup():
            manager = SecretManager(vault_client=vault_client)
            manager.set_simple_secret("omapi-key", "omapi-secret")
            manager.delete_secret("omapi-key")

        yield deferToDatabase(setup)

        yield deferToDatabase(self.service._run)
        yield deferToDatabase(self.service._run)
        self.assertEqual(
            mock_delete.mock_calls,
            [call("global/omapi-key"), call("global/omapi-key")],
        )
