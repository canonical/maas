# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: get the named configuration snippet used to hook
up MAAS' DNS configuration files with an existing DNS server.
"""

__all__ = [
    'Command',
    ]


from django.core.management.base import BaseCommand
from provisioningserver.dns.config import DNSConfig


INCLUDE_SNIPPET_COMMENT = """\
# Append the following content to your local BIND configuration
# file (usually /etc/bind/named.conf.local) in order to allow
# MAAS to manage its DNS zones.
"""


class Command(BaseCommand):
    help = (
        "Return the named configuration snippet used to include "
        "MAAS' DNS configuration in an existing named "
        "configuration.")

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument(
            '--edit', action='store_true', dest='edit',
            default=False,
            help="Edit the configuration file instead of simply "
                 "printing the snippet.")
        parser.add_argument(
            '--config_path', dest='config_path',
            default='/etc/bind/named.conf.local',
            help="Specifies the configuration file location ("
                 "used in conjonction with --edit). Defaults to "
                 "/etc/bind/named.conf.local.")

    def handle(self, *args, **options):
        edit = options.get('edit')
        config_path = options.get('config_path')
        include_snippet = DNSConfig.get_include_snippet()

        if edit is True:
            # XXX: GavinPanella: I've not been able to discover what character
            # set BIND expects for its configuration, so I've gone with a safe
            # choice of ASCII. If we find that this fails we can revisit this
            # and experiment to discover a better choice.
            with open(config_path, "a", encoding="ascii") as conf_file:
                conf_file.write(include_snippet)
        else:
            return INCLUDE_SNIPPET_COMMENT + include_snippet
