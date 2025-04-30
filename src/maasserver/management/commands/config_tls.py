# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: configure regiond listener."""

import argparse

from django.db import DEFAULT_DB_ALIAS

from maascli.init import prompt_yes_no
from maasserver.enum import ENDPOINT
from maasserver.listener import notify
from maasserver.management.commands.base import BaseCommandWithConnection
from provisioningserver.certificates import Certificate
from provisioningserver.events import EVENT_TYPES


def _update_tls_config(
    config_manager, key=None, cert=None, cacert=None, port=None
):
    from maasserver.audit import create_audit_event
    from maasserver.regiondservices.certificate_expiration_check import (
        clear_tls_notifications,
    )
    from maasserver.secrets import SecretManager

    secrets = {
        "key": key,
        "cert": cert,
        "cacert": cacert,
    }
    secret_manager = SecretManager()
    if any(secrets.values()):
        secret_manager.set_composite_secret("tls", secrets)
    else:
        secret_manager.delete_secret("tls")

    config_manager.set_config("tls_port", port)

    create_audit_event(
        EVENT_TYPES.SETTINGS,
        ENDPOINT.CLI,
        description="Updated TLS configuration settings",
    )
    clear_tls_notifications()
    # send a notification about the config change
    notify("sys_reverse_proxy")


class Command(BaseCommandWithConnection):
    help = "Configure MAAS Region TLS."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="command")
        subparsers.required = True

        enable_tls_parser_append = subparsers.add_parser(
            "enable",
            help="Enable TLS and switch to a secured mode (https).",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        subparsers.add_parser(
            "disable",
            help="Disable TLS and switch to a non-secured mode (http).",
        )

        enable_tls_parser_append.add_argument(
            "key", help="path to the private key", type=argparse.FileType()
        )
        enable_tls_parser_append.add_argument(
            "cert",
            help="path to certificate in PEM format",
            type=argparse.FileType(),
        )
        enable_tls_parser_append.add_argument(
            "--cacert",
            help="path to CA certificates chain in PEM format",
            type=argparse.FileType(),
        )
        enable_tls_parser_append.add_argument(
            "-p", "--port", help="HTTPS port", default=5443, type=int
        )
        enable_tls_parser_append.add_argument(
            "--yes",
            help="Skip interactive confirmation",
            action="store_true",
            default=False,
        )

    def handle(self, *args, **options):
        from maasserver.models import Config

        config_manager = Config.objects.db_manager(DEFAULT_DB_ALIAS)

        if options["command"] == "disable":
            _update_tls_config(config_manager)
            return

        if not options["yes"]:
            reply = prompt_yes_no(
                "Once TLS is enabled, the MAAS UI and API won't be accessible over HTTP anymore, proceed? (y/n): "
            )
            if not reply:
                return

        cacerts = options["cacert"].read() if options["cacert"] else ""
        cert = Certificate.from_pem(
            options["key"].read(),
            options["cert"].read(),
            ca_certs_material=cacerts,
        )
        _update_tls_config(
            config_manager,
            key=cert.private_key_pem(),
            cert=cert.certificate_pem(),
            cacert=cert.ca_certificates_pem(),
            port=options["port"],
        )
