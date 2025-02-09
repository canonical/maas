# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Edit the named.conf.options file so that it includes
the named.conf.options.inside.maas file, which contains the 'forwarders'
setting.
"""

from collections import OrderedDict
import sys
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError

from maasserver.models import Config
from provisioningserver.dns.commands.edit_named_options import (
    add_arguments,
    edit_options,
)


class Command(BaseCommand):
    help = " ".join(
        dedent(
            """\
    Edit the named.conf.options file so that it includes the
    named.conf.options.inside.maas file, which contains the 'forwarders' and
    'dnssec-validation' settings. A backup of the old file will be made with
    the suffix '.maas-YYYY-MM-DDTHH:MM:SS.mmmmmm'. All configuration files are
    treated as 7-bit ASCII; it's not clear what else BIND will tolerate. This
    program must be run as root.
    """
        ).splitlines()
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        add_arguments(parser)
        parser.add_argument(
            "--migrate-conflicting-options",
            default=False,
            dest="migrate_conflicting_options",
            action="store_true",
            help="**This option is now deprecated**. It no longer has any "
            "effect and it may be removed in a future release.",
        )

    def migrate_forwarders(self, options_block, dry_run, stdout):
        """Remove existing forwarders from the options block.

        It's a syntax error to have more than one in the combined
        configuration for named, so we just remove whatever was there.

        Migrate any forwarders in the configuration file to the MAAS config.
        """
        if "forwarders" in options_block:
            bind_forwarders = options_block["forwarders"]

            delete_forwarders = False
            if not dry_run:
                try:
                    config, created = Config.objects.get_or_create(
                        name="upstream_dns",
                        defaults={"value": " ".join(bind_forwarders)},
                    )
                    if not created:
                        # A configuration value already exists, so add the
                        # additional values we found in the configuration
                        # file to MAAS.
                        if config.value is None:
                            config.value = ""
                        maas_forwarders = OrderedDict.fromkeys(
                            config.value.split()
                        )
                        maas_forwarders.update(bind_forwarders)
                        config.value = " ".join(maas_forwarders)
                        config.save()
                    delete_forwarders = True
                except Exception:
                    pass
            else:
                stdout.write(
                    "// Append to MAAS forwarders: %s\n"
                    % " ".join(bind_forwarders)
                )

            # Only delete forwarders from the config if MAAS was able to
            # migrate the options. Otherwise leave them in the original
            # config.
            if delete_forwarders:
                del options_block["forwarders"]

    def migrate_dnssec_validation(self, options_block, dry_run, stdout):
        """Remove existing dnssec-validation from the options block.

        It's a syntax error to have more than one in the combined
        configuration for named so we just remove whatever was there.
        There is no data loss due to the backup file made later.

        Migrate this value in the configuration file to the MAAS config.
        """
        if "dnssec-validation" in options_block:
            dnssec_validation = options_block["dnssec-validation"]

            if not dry_run:
                try:
                    config, created = Config.objects.get_or_create(
                        name="dnssec_validation",
                        defaults={"value": dnssec_validation},
                    )
                    if not created:
                        # Update the MAAS configuration to reflect the new
                        # setting found in the configuration file.
                        config.value = dnssec_validation
                        config.save()
                except Exception:
                    pass
            else:
                stdout.write(
                    "// Set MAAS dnssec_validation to: %s\n"
                    % dnssec_validation
                )
            # Always attempt to delete this option as MAAS will always create
            # a default for it.
            del options_block["dnssec-validation"]

    def handle(self, *args, **options):
        """Entry point for BaseCommand."""
        config_path = options.get("config_path")
        dry_run = options.get("dry_run")
        force = options.get("force")
        stdout = options.get("stdout")
        if stdout is None:
            stdout = sys.stdout

        def options_handler(options_block):
            self.migrate_forwarders(options_block, dry_run, stdout)
            self.migrate_dnssec_validation(options_block, dry_run, stdout)

        try:
            edit_options(config_path, stdout, dry_run, force, options_handler)
        except ValueError as exc:
            raise CommandError(str(exc)) from None
