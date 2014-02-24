# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Edit the named.conf.options file so that it includes
the named.conf.options.inside.maas file, which contains the 'forwarders'
setting.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Command',
    ]

from datetime import datetime
from optparse import make_option
import os
import shutil

from django.core.management.base import (
    BaseCommand,
    CommandError,
    )
from iscpy import (
    MakeISC,
    ParseISCString,
    )
from provisioningserver.dns.config import MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME


class Command(BaseCommand):

    option_list = BaseCommand.option_list + (
        make_option(
            '--config-path', dest='config_path',
            default="/etc/bind/named.conf.options",
            help="Specify the configuration file to edit."),
    )
    help = (
        "Edit the named.conf.options file so that it includes the "
        "named.conf.options.inside.maas file, which contains the "
        "'forwarders' setting.  A backup of the old file will be made "
        "with the suffix '.maas-YYYY-MM-DDTHH:MM:SS.mmmmmm'.  This "
        "program must be run as root.")

    def read_file(self, config_path):
        """Open the named file and return its contents as a string."""
        if not os.path.exists(config_path):
            raise CommandError("%s does not exist" % config_path)

        with open(config_path, "rb") as fd:
            options_file = fd.read()
        return options_file

    def parse_file(self, config_path, options_file):
        """Read the named.conf.options file and parse it with iscpy.

        We also use iscpy to insert the include statement that we need.
        """
        try:
            config_dict = ParseISCString(options_file)
        except Exception as e:
            # Yes, it throws bare exceptions :(
            raise CommandError("Failed to parse %s: %s" % (
                config_path, e.message))
        options_block = config_dict.get("options", None)
        if options_block is None:
            # Something is horribly wrong with the file, bail out rather
            # than doing anything drastic.
            raise CommandError(
                "Can't find options {} block in %s, bailing out without "
                "doing anything." % config_path)
        return config_dict

    def set_up_include_statement(self, options_block, config_path):
        """Insert the 'include' directive into the iscpy-parsed options."""
        dir = os.path.dirname(config_path)
        options_block['include'] = '"%s/%s"' % (
            dir, MAAS_NAMED_CONF_OPTIONS_INSIDE_NAME)

    def remove_forwarders(self, options_block):
        """Remove existing forwarders from the options block.

        It's a syntax error to have more than one in the combined
        configuration for named so we just remove whatever was there.
        There is no data loss due to the backup file made later.
        """
        if 'forwarders' in options_block:
            del options_block['forwarders']

    def back_up_existing_file(self, config_path):
        now = datetime.now().isoformat()
        backup_destination = config_path + '.' + now
        try:
            shutil.copyfile(config_path, backup_destination)
        except IOError as e:
            raise CommandError(
                "Failed to make a backup of %s, exiting: %s" % (
                    config_path, e.message))

    def handle(self, *args, **options):
        """Entry point for BaseCommand."""
        # Read stuff in, validate.
        config_path = options.get('config_path')
        options_file = self.read_file(config_path)
        config_dict = self.parse_file(config_path, options_file)
        options_block = config_dict['options']

        # Modify the config.
        self.set_up_include_statement(options_block, config_path)
        self.remove_forwarders(options_block)
        new_content = MakeISC(config_dict)

        # Back up and write new file.
        self.back_up_existing_file(config_path)
        with open(config_path, "wb") as fd:
            fd.write(new_content)
