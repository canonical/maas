# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Get the named configuration snippet used to hook up MAAS' DNS configuration
files with an existing DNS server.
"""

import sys
from textwrap import dedent

from provisioningserver.dns.config import DNSConfig

INCLUDE_SNIPPET_COMMENT = """\
# Append the following content to your local BIND configuration
# file (usually /etc/bind/named.conf.local) in order to allow
# MAAS to manage its DNS zones.
"""


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Return the named configuration snippet used to include
        MAAS' DNS configuration in an existing named configuration.
        """
    )
    parser.add_argument(
        "--edit",
        action="store_true",
        dest="edit",
        default=False,
        help="Edit the configuration file instead of simply "
        "printing the snippet.",
    )
    parser.add_argument(
        "--config-path",
        dest="config_path",
        default="/etc/bind/named.conf.local",
        help="Specifies the configuration file location ("
        "used in conjonction with --edit). Defaults to "
        "/etc/bind/named.conf.local.",
    )


def run(args, stdout=sys.stdout, stderr=sys.stderr):
    """Return the named configuration snippet.

    :param args: Parsed output of the arguments added in `add_arguments()`.
    :param stdout: Standard output stream to write to.
    :param stderr: Standard error stream to write to.
    """
    include_snippet = DNSConfig.get_include_snippet()

    if args.edit is True:
        # XXX: GavinPanella: I've not been able to discover what character
        # set BIND expects for its configuration, so I've gone with a safe
        # choice of ASCII. If we find that this fails we can revisit this
        # and experiment to discover a better choice.
        with open(args.config_path, "a", encoding="ascii") as conf_file:
            conf_file.write(include_snippet)
    else:
        stdout.write(INCLUDE_SNIPPET_COMMENT + include_snippet)
        stdout.write("\n")
        stdout.flush()
