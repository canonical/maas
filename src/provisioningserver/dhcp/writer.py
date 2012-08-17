# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate a DHCP server configuration."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "add_arguments",
    "run",
    ]

import sys

from provisioningserver.dhcp import config


def add_arguments(parser):
    """Initialise options for generating DHCP configuration.

    :param parser: An instance of :class:`ArgumentParser`.
    """
    parser.add_argument(
        "--subnet", action="store", required=True, help=(
        "Base subnet declaration, e.g. 192.168.1.0"))
    parser.add_argument(
        "--subnet-mask", action="store", required=True, help=(
            "The mask for the subnet, e.g. 255.255.255.0"))
    parser.add_argument(
        "--next-server", action="store", required=True, help=(
            "The address of the TFTP server"))
    parser.add_argument(
        "--broadcast-ip", action="store", required=True, help=(
            "The broadcast IP address for the subnet, e.g. 192.168.1.255"))
    parser.add_argument(
        "--dns-servers", action="store", required=True, help=(
            "One or more IP addresses of the DNS server for the subnet "
            "separated by spaces."))
    parser.add_argument(
        "--router-ip", action="store", required=True, help=(
            "The router/gateway IP address for the subnet"))
    parser.add_argument(
        "--ip-range-low", action="store", required=True, help=(
            "The first IP address in the range of IP addresses to "
            "allocate"))
    parser.add_argument(
        "--ip-range-high", action="store", required=True, help=(
            "The last IP address in the range of IP addresses to "
            "allocate"))
    parser.add_argument(
        "--omapi-key", action="store", required=True, help=(
            "The shared key for authentication to OMAPI"))
    parser.add_argument(
        "-o", "--outfile", action="store", required=False, help=(
            "A file to save to. When left unspecified the configuration "
            "will be written to stdout. This option is useful when "
            "running outside of a shell."))


def run(args):
    """Generate a DHCP server configuration, and write it to stdout."""
    params = vars(args)
    output = config.get_config(**params).encode("ascii")
    if args.outfile is None:
        sys.stdout.write(output)
    else:
        with open(args.outfile, "wb") as out:
            out.write(output)
