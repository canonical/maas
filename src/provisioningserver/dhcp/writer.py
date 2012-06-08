# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utility script to write out a dhcp server config from cmd line params."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import argparse
from sys import stdout

from provisioningserver.dhcp import config


class DHCPConfigWriter:

    def __init__(self):
        self.set_up_args()

    def set_up_args(self):
        """Initialise an ArgumentParser's options."""
        self.parser = argparse.ArgumentParser(description=__doc__)
        self.parser.add_argument(
            "--subnet", action="store", required=True, help=(
                "Base subnet declaration, e.g. 192.168.1.0"))
        self.parser.add_argument(
            "--subnet-mask", action="store", required=True, help=(
                "The mask for the subnet, e.g. 255.255.255.0"))
        self.parser.add_argument(
            "--next-server", action="store", required=True, help=(
                "The address of the TFTP server"))
        self.parser.add_argument(
            "--broadcast-address", action="store", required=True,
            help=(
                "The broadcast IP address for the subnet, "
                "e.g. 192.168.1.255"))
        self.parser.add_argument(
            "--dns-servers", action="store", required=True, help=(
                "One or more IP addresses of the DNS server for the subnet "
                "separated by spaces."))
        self.parser.add_argument(
            "--gateway", action="store", required=True, help=(
                "The router/gateway IP address for the subnet"))
        self.parser.add_argument(
            "--low-range", action="store", required=True, help=(
                "The first IP address in the range of IP addresses to "
                "allocate"))
        self.parser.add_argument(
            "--high-range", action="store", required=True, help=(
                "The last IP address in the range of IP addresses to "
                "allocate"))
        self.parser.add_argument(
            "--out-file", action="store", required=False, help=(
                "The file to write the config.  If not set will write "
                "to stdout"))

    def parse_args(self, argv=None):
        """Parse provided argv or default to sys.argv."""
        return self.parser.parse_args(argv)

    def generate(self, args):
        """Generate the config."""
        params = args.__dict__
        output = config.get_config(**params)
        return output

    def run(self, argv=None):
        """Generate the config and write to stdout or a file as required."""
        args = self.parse_args(argv)
        output = self.generate(args).encode("ascii")
        if args.out_file is not None:
            with open(args.out_file, "wb") as f:
                f.write(output)
        else:
            stdout.write(output)


if __name__ == "__main__":
    DHCPConfigWriter().run()
