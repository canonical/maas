# Copyright 2012-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: configure regiond listener."""

import argparse

from django.core.management.base import BaseCommand
from django.db import DEFAULT_DB_ALIAS, transaction

from maascli.init import read_input
from maasserver.models import Config
from provisioningserver.certificates import Certificate


def set_tls_config(config_manager, cert, port):
    with transaction.atomic():
        config_manager.set_config("tls_port", port)
        config_manager.set_config("tls_key", cert.private_key_pem())
        config_manager.set_config("tls_cert", cert.certificate_pem())


def disable_tls(config_manager):
    with transaction.atomic():
        config_manager.set_config("tls_port", None)
        config_manager.set_config("tls_key", "")
        config_manager.set_config("tls_cert", "")


class Command(BaseCommand):
    help = "Configure MAAS Region TLS."

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="command")
        subparsers.required = True

        enable_tls_parser_append = subparsers.add_parser(
            "enable", help="Enable TLS and switch to a secured mode (https)."
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
            "-p", "--port", help="HTTPS port", default=5443, type=int
        )

    def handle(self, *args, **options):
        config_manager = Config.objects.db_manager(DEFAULT_DB_ALIAS)

        if options["command"] == "disable":
            disable_tls(config_manager)
            return

        reply = (
            read_input(
                "Once TLS is enabled, the MAAS UI and API won't be accessible over HTTP anymore, proceed? (y/n): "
            )
            .lower()
            .strip()
        )
        if reply != "y":
            return

        cert = Certificate.from_pem(
            options["key"].read(), options["cert"].read()
        )

        set_tls_config(config_manager, cert, options["port"])
