# Copyright 2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: configure vault integration."""

import argparse
from textwrap import dedent
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from hvac.exceptions import VaultError
from requests.exceptions import ConnectionError

from maascli.init import prompt_yes_no
from maasserver.vault import (
    configure_region_with_vault,
    get_region_vault_client,
    WrappedSecretError,
)


class Command(BaseCommand):
    help = "(placeholder) Configure MAAS Region Vault integration."
    CONFIGURE_COMMAND = "configure"

    @staticmethod
    def _configure_vault(
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
            configure_region_with_vault(
                url=vault_url,
                role_id=approle_id,
                wrapped_token=wrapped_token,
                secrets_path=secrets_path,
                secrets_mount=mount,
            )
            return dedent(
                """
                Vault successfully configured for the region!
                Once all regions in cluster are configured, use the following command to migrate secrets:

                sudo maas config-vault migrate

                """
            )
        except (ConnectionError, VaultError, WrappedSecretError) as e:
            raise CommandError(e)

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(
            dest="command",
            # XXX: remove SUPPRESS once the command is publicly available
            help=argparse.SUPPRESS,
        )
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

    def handle(self, *args, **options):
        if options["command"] == self.CONFIGURE_COMMAND:
            return self._configure_vault(
                options["url"],
                options["role_id"],
                options["wrapped_token"],
                options["secrets_path"].rstrip("/"),
                options["yes"],
                options["mount"].rstrip("/"),
            )
