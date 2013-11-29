#!/usr/bin/env python2.7
# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Probe network on given network interface for a DHCP server.

This needs to be run as root, in order to be allowed to broadcast on the
BOOTP port.

Exit code is zero ("success") if no servers were detected, or the number of
DHCP servers that were found.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

import argparse
from sys import exit

from provisioningserver.dhcp.detect import probe_dhcp

argument_parser = argparse.ArgumentParser(description=__doc__)


def main():
    argument_parser.add_argument(
        'interface',
        help="Probe network on this network interface.")

    args = argument_parser.parse_args()

    servers = probe_dhcp(args.interface)

    num_servers = len(servers)
    if num_servers == 0:
        print("No DHCP servers detected.")
        exit(0)
    else:
        print("DHCP servers detected: %s" % ', '.join(sorted(servers)))
        exit(num_servers)

if __name__ == "__main__":
    main()
