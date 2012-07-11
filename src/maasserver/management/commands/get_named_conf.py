# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: get the named configuration snippet used to hook
up MAAS' DNS configuration files with an existing DNS server.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


from optparse import make_option

from django.core.management.base import BaseCommand
from provisioningserver.dns.config import DNSConfig


INCLUDE_SNIPPET_COMMENT = """
# Append the following content to your  local BIND configuration
# file (usually /etc/bind/named.conf.local) in order to allow
# MAAS to manage its DNS zones.
"""


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--edit', action='store_true', dest='edit',
            default=False,
            help="Edit the configuration file instead of simply "
                 "printing the snippet."),
        make_option(
            '--config_path', dest='config_path',
            default='/etc/bind/named.conf.local',
            help="Specifies the configuration file location ("
                 "used in conjonction with --edit). Defaults to "
                 "/etc/bind/named.conf.local."),
      )
    help = (
        "Return the named configuration snippet used to include "
        "MAAS' DNS configuration in an existing named "
        "configuration.")

    def handle(self, *args, **options):
        edit = options.get('edit')
        config_path = options.get('config_path')
        include_snippet = DNSConfig().get_include_snippet()

        if edit is True:
            with open(config_path, "ab") as conf_file:
                conf_file.write(include_snippet)
        else:
            return INCLUDE_SNIPPET_COMMENT + include_snippet
