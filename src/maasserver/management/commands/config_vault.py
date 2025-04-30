# Copyright 2022-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: configure vault integration."""

import argparse
from textwrap import dedent
import time
from typing import Optional

from django.core.management.base import CommandError
import yaml

from maascli.init import prompt_yes_no
from maasserver.enum import NODE_TYPE
from maasserver.listener import notify
from maasserver.locks import startup
from maasserver.management.commands.base import BaseCommandWithConnection
from maasserver.utils import synchronised
from maasserver.vault import (
    configure_region_with_vault,
    get_region_vault_client,
    VaultError,
    WrappedSecretError,
)
from provisioningserver.utils.env import MAAS_ID


class Command(BaseCommandWithConnection):
    help = "Configure MAAS Region Vault integration."
    CONFIGURE_COMMAND = "configure"
    MIGRATE_COMMAND = "migrate"
    STATUS_COMMAND = "status"

    def _set_vault_configured_db_flag(self) -> bool:
        """Set the DB flag saying Vault is configured for region"""
        from maasserver.models import ControllerInfo, RegionController

        if not MAAS_ID.get():
            return False

        try:
            node = RegionController.objects.get_running_controller()
        except RegionController.DoesNotExist:
            # No RegionController? No problem, region will create
            # one on startup and the flag will be set if Vault
            # is configured.
            return False
        ControllerInfo.objects.filter(node_id=node.id).update(
            vault_configured=True
        )
        return True

    def _configure_vault(
        self,
        vault_url: str,
        approle_id: str,
        wrapped_token: str,
        secrets_path: str,
        ignore_existing: bool,
        mount: str,
    ) -> Optional[str]:
        if not ignore_existing and get_region_vault_client() is not None:
            reply = prompt_yes_no(
                "This region already has Vault configured. Overwrite the existing vault configuration? (y/n): "
            )
            if not reply:
                return

        try:
            # Populate region configuration
            configure_region_with_vault(
                url=vault_url,
                role_id=approle_id,
                wrapped_token=wrapped_token,
                secrets_path=secrets_path,
                secrets_mount=mount,
            )
            # Set DB flag (if possible) to avoid having to restart
            # the region in order to migrate the secrets.
            self._set_vault_configured_db_flag()

            return dedent(
                """
                Vault successfully configured for the region!
                Once all regions in cluster are configured, use the following command to migrate secrets:

                sudo maas config-vault migrate

                """
            )
        except VaultError as e:
            raise CommandError(e.__cause__)  # noqa: B904
        except WrappedSecretError as e:
            raise CommandError(e)  # noqa: B904

    def _get_online_regions(self) -> list[str]:
        """Returns the list of online regions"""
        from maasserver.models import Node

        return list(
            Node.objects.filter(
                node_type__in=[
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                ],
                processes__isnull=False,
            )
            .distinct()
            .values_list("hostname", flat=True)
            .order_by("hostname")
        )

    def _restart_regions(self):
        """Notifies regions to restart and monitors their status based on PostgreSQL activity"""
        # Retry restarting all the regions
        print("Send restart signal to active regions")
        notify("sys_vault_migration")
        print(" - Signal sent. Waiting for 5 seconds...")
        time.sleep(5)
        attempts_allowed = 10
        for attempt in range(1, attempts_allowed + 1):
            print(
                f"\nWait for active regions to restart (attempt {attempt}/{attempts_allowed})"
            )
            regions = self._get_online_regions()
            if not regions:
                print(" - No regions are currently active, proceeding.")
                return
            print(f" - Regions are still active: {', '.join(regions)}")
            if attempt != attempts_allowed:
                # Don't wait for the last attempt
                time.sleep(5)

        # Retries limit exceeded, raise an error
        raise CommandError(
            "Unable to migrate as one or more regions didn't restart when politely asked. "
            "Please shut down these regions before starting the migration process again."
        )

    def _migrate_secrets(self, client):
        """Handles the actual secrets migration"""
        from maasserver.models import Config, Secret, VaultSecret

        print("Migrating secrets")
        metadata = []
        for secret in Secret.objects.all():
            client.set(secret.path, secret.value)
            metadata.append(VaultSecret(path=secret.path, deleted=False))
            secret.delete()

        VaultSecret.objects.bulk_create(metadata)

        # Enable Vault cluster-wide
        Config.objects.set_config("vault_enabled", True)

    def _get_unconfigured_regions(self) -> list[str]:
        """Return a list of names of regions that are not configured for Vault"""
        from maasserver.models import ControllerInfo

        return list(
            ControllerInfo.objects.filter(vault_configured=False)
            .values_list("node__hostname", flat=True)
            .order_by("node__hostname")
        )

    @synchronised(startup)
    def _handle_migrate(self, options):
        from maasserver.models import Config
        from maasserver.utils.orm import transactional

        if Config.objects.get_config("vault_enabled", False):
            raise CommandError("Secrets are already migrated to Vault.")

        client = get_region_vault_client()
        # Check if current region has Vault client configured
        if not client:
            raise CommandError(
                "Vault is not configured for the current region. "
                "Please use `sudo maas config-vault configure` command on all regions before migrating."
            )

        # Check if all the other regions have Vault client configured
        unconfigured_regions = self._get_unconfigured_regions()
        if unconfigured_regions:
            raise CommandError(
                f"Vault is not configured for regions: {', '.join(unconfigured_regions)}\n"
                "Please use `sudo maas config-vault configure` command on the regions above before migrating."
            )

        # Check if vault is available (so that we won't restart regions for nothing)
        try:
            client.check_authentication()
        except VaultError as e:
            raise CommandError(f"Vault test failed: {e.__cause__}")  # noqa: B904
        # Restart regions to ensure there will be no regions trying to write secrets to the DB during migration
        self._restart_regions()
        # Now we're ready to perform the actual migration
        transactional(self._migrate_secrets(client))

        return "Successfully migrated cluster secrets to Vault"

    def _handle_status(self, options):
        from maasserver.models import Config

        vault_enabled = Config.objects.get_config("vault_enabled", False)
        report = {"status": "enabled" if vault_enabled else "disabled"}
        if not vault_enabled:
            report["unconfigured_regions"] = self._get_unconfigured_regions()
        print(yaml.safe_dump(report), end=None)

    def _handle_configure(self, options):
        return self._configure_vault(
            options["url"],
            options["role_id"],
            options["wrapped_token"],
            options["secrets_path"].rstrip("/"),
            options["yes"],
            options["mount"].rstrip("/"),
        )

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="command")
        subparsers.required = True

        configure_vault_parser_append = subparsers.add_parser(
            self.CONFIGURE_COMMAND,
            help="Update MAAS configuration to use Vault secret storage.",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )
        configure_vault_parser_append.add_argument("url", help="Vault URL")
        configure_vault_parser_append.add_argument(
            "role_id", help="Vault AppRole Role ID"
        )
        configure_vault_parser_append.add_argument(
            "wrapped_token",
            help="Vault wrapped token for the AppRole secret_id",
        )
        configure_vault_parser_append.add_argument(
            "secrets_path",
            help="Path prefix for MAAS secrets in Vault KV storage",
        )
        configure_vault_parser_append.add_argument(
            "--mount", help="Vault KV mount path", default="secret"
        )
        configure_vault_parser_append.add_argument(
            "--yes",
            help="Skip interactive confirmation",
            action="store_true",
            default=False,
        )

        subparsers.add_parser(
            self.MIGRATE_COMMAND,
            help="Migrate secrets to Vault",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        subparsers.add_parser(
            self.STATUS_COMMAND,
            help="Report status of Vault integration",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

    def handle(self, *args, **options):
        handlers = {
            self.CONFIGURE_COMMAND: self._handle_configure,
            self.MIGRATE_COMMAND: self._handle_migrate,
            self.STATUS_COMMAND: self._handle_status,
        }
        return handlers[options["command"]](options)
