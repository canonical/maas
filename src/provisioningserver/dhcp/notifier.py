# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Write DHCP action notification to the `dhcpd.sock`."""

__all__ = [
    "add_arguments",
    "run",
    ]

import argparse
from contextlib import closing
import json
import socket
import time


def add_arguments(parser):
    """Initialise options for sending DHCP notification over the dhcpd.sock.

    :param parser: An instance of :class:`ArgumentParser`.
    """
    parser.add_argument(
        "--action", action="store", required=True,
        choices=['commit', 'expiry', 'release'], help=(
            "Action taken by DHCP server for the lease."))
    parser.add_argument(
        "--mac", action="store", required=True, help=(
            "MAC address for lease."))
    parser.add_argument(
        "--ip-family", action="store", required=True, choices=['ipv4', 'ipv6'],
        help="IP address family for lease.")
    parser.add_argument(
        "--ip", action="store", required=True, help=(
            "IP address for lease."))
    parser.add_argument(
        "--lease-time", action="store", type=int, required=False, help=(
            "Length of time before the lease expires."))
    parser.add_argument(
        "--hostname", action="store", required=False, help=(
            "Hostname of the machine for the lease."))
    parser.add_argument(
        "--socket", action="store", required=False,
        default="/var/lib/maas/dhcpd.sock", help=argparse.SUPPRESS)


def run(args):
    """Write DHCP action notification to the `dhcpd.sock`."""
    notify_packet = {
        "action": args.action,
        "mac": args.mac,
        "ip_family": args.ip_family,
        "ip": args.ip,
        "timestamp": int(time.time()),
    }

    # Lease time is required by the commit action and hostname is optional.
    if args.action == "commit":
        notify_packet["lease_time"] = args.lease_time
        hostname = args.hostname
        has_hostname = (
            hostname is not None and
            len(hostname) > 0 and
            not hostname.isspace())
        if has_hostname:
            notify_packet["hostname"] = hostname

    # Connect to the socket and send the packet over as JSON.
    payload = json.dumps(notify_packet)
    conn = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    conn.connect(args.socket)
    with closing(conn):
        conn.send(payload.encode("utf-8"))
