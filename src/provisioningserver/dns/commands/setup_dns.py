# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Setup the MAAS named configuration.

This creates a basic, blank DNS configuration which will allow MAAS to
reload its configuration once zone files will be written.

The main purpose of this command is for it to be run when 'maas-region-api' or
'maas-rack-controller' is installed.
"""

import sys
from textwrap import dedent

from provisioningserver.dns.config import (
    DNSConfig,
    set_up_nsupdate_key,
    set_up_options_conf,
    set_up_rndc,
    set_up_zone_file_dir,
)


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Setup MAAS DNS configuration: a blank configuration and
        all the RNDC configuration options allowing MAAS to reload
        BIND once zones configuration files will be written.
        """
    )
    parser.add_argument(
        "--no-clobber",
        dest="no_clobber",
        action="store_true",
        default=False,
        help="Don't overwrite the configuration file if it already exists.",
    )


def run(args, stdout=sys.stdout, stderr=sys.stderr):
    """Setup MAAS DNS configuration.

    :param args: Parsed output of the arguments added in `add_arguments()`.
    :param stdout: Standard output stream to write to.
    :param stderr: Standard error stream to write to.
    """
    set_up_nsupdate_key()
    set_up_zone_file_dir()
    set_up_rndc()
    set_up_options_conf(overwrite=not args.no_clobber)
    config = DNSConfig()
    config.write_config(
        overwrite=not args.no_clobber, zone_names=(), reverse_zone_names=()
    )
