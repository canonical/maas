#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import logging
import os
import signal

from asyncpg import Connection

from maasapiserver.common.listeners.postgres import PostgresListener

logger = logging.getLogger(__name__)


class VaultMigrationPostgresListener(PostgresListener):
    VAULT_MIGRATION_CHANNEL = "sys_vault_migration"

    def __init__(self):
        super().__init__(self.VAULT_MIGRATION_CHANNEL)

    def handler(
        self, connection: Connection, pid: int, channel: str, payload: str
    ):
        # Vault is being configured and a restart has been requested by the cli command. The underlying service orchestrator will spin again the application.
        logger.info(
            "sys_vault_migration notification has been received. Shutting down the application."
        )
        os.kill(os.getpid(), signal.SIGTERM)
