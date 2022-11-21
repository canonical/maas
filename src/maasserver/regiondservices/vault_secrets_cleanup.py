from contextlib import suppress
from datetime import timedelta
import logging

from django.db import transaction
from twisted.internet.defer import inlineCallbacks

from maasserver.models import VaultSecret
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.vault import (
    get_region_vault_client_if_enabled,
    VaultClient,
    VaultError,
)
from provisioningserver.utils.services import SingleInstanceService
from provisioningserver.utils.twisted import synchronous

logger = logging.getLogger(__name__)


class VaultSecretsCleanupService(SingleInstanceService):
    """Service to periodically remove deleted secrets from Vault.

    When secrets are removed they're not immediately deleted from Vault, but
    only marked for deletion.  This service periodically removes them from
    Vault.  The intent is to avoid accidentally loss due to a transaction
    failure after removing from Vault, which would make it impossible to
    rollback.
    """

    LOCK_NAME = SERVICE_NAME = "vault-secrets-cleanup"
    INTERVAL = timedelta(seconds=60)

    @inlineCallbacks
    def do_action(self):
        yield deferToDatabase(self._run)

    @synchronous
    @transactional
    def _run(self):
        client = get_region_vault_client_if_enabled()
        if not client:
            return

        self._clean_secrets(client)

    def _clean_secrets(self, client: VaultClient):
        deleted_paths = list(
            VaultSecret.objects.filter(deleted=True).values_list(
                "path", flat=True
            )
        )
        if not deleted_paths:
            return

        logger.info(
            f"processing deletion of {len(deleted_paths)} secrets in Vault"
        )
        for path in deleted_paths:
            with (
                suppress(transaction.TransactionManagementError),
                transaction.atomic(),
                suppress(VaultError),
            ):
                client.delete(path)
                self._delete_secret_entry(path)

    def _delete_secret_entry(self, path: str):
        VaultSecret.objects.filter(path=path).delete()
