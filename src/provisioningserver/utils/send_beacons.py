# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for sending and receiving beacons on attached networks."""


from pprint import pformat
import sys
from textwrap import dedent

from provisioningserver import logger
from provisioningserver.logger import DEFAULT_LOG_VERBOSITY, LegacyLogger
from provisioningserver.utils.beaconing import (
    BEACON_IPV4_MULTICAST,
    BEACON_PORT,
    create_beacon_payload,
)
from provisioningserver.utils.network import (
    get_all_interfaces_definition,
    get_ifname_ifdata_for_destination,
)
from provisioningserver.utils.services import (
    BeaconingSocketProtocol,
    interface_info_to_beacon_remote_payload,
)

log = LegacyLogger()


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Send solicitation beacons to a particular address.
        """
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        help="Verbose packet output.",
    )
    parser.add_argument(
        "-s",
        "--source",
        type=str,
        required=False,
        help="Source address to send beacons from.",
    )
    parser.add_argument(
        "-t",
        "--timeout",
        type=int,
        required=False,
        default=5,
        help="Number of seconds to wait for beacons.",
    )
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        required=False,
        default=0,
        help="Port to listen for beacons on. By default, listens on a random "
        "port.",
    )
    parser.add_argument(
        "destination",
        type=str,
        nargs="?",
        help="Destination to send beacon to. If not specified, will use the "
        "MAAS multicast group (224.0.0.118 or ff02::15a) on all "
        "interfaces.",
    )


def do_beaconing(args, interfaces=None, reactor=None):
    """Sends out beacons based on the given arguments, and waits for replies.

    :param args: The command-line arguments.
    :param interfaces: The interfaces to send out beacons on.
        Must be the result of `get_all_interfaces_definition()`.
    """
    if reactor is None:
        from twisted.internet import reactor
    if args.source is None:
        source_ip = "::"
    else:
        source_ip = args.source
    protocol = BeaconingSocketProtocol(
        reactor,
        process_incoming=True,
        debug=True,
        interface=source_ip,
        port=args.port,
        interfaces=interfaces,
    )
    if args.destination is None:
        destination_ip = "::ffff:" + BEACON_IPV4_MULTICAST
    elif ":" not in args.destination:
        destination_ip = "::ffff:" + args.destination
    else:
        destination_ip = args.destination
    if "224.0.0.118" in destination_ip:
        protocol.send_multicast_beacons(interfaces, verbose=args.verbose)
    else:
        log.msg("Sending unicast beacon to '%s'..." % destination_ip)
        ifname, ifdata = get_ifname_ifdata_for_destination(
            destination_ip, interfaces
        )
        remote = interface_info_to_beacon_remote_payload(ifname, ifdata)
        payload = {"remote": remote}
        beacon = create_beacon_payload("solicitation", payload=payload)
        protocol.send_beacon(beacon, (destination_ip, BEACON_PORT))
    reactor.callLater(args.timeout, lambda: reactor.stop())
    reactor.run()
    return protocol


def run(args, stdout=sys.stdout):
    """Sends out beacons, waits for replies, and optionally print debug info.

    :param args: Parsed output of the arguments added in `add_arguments()`.
    :param stdout: Standard output stream to write to.
    """
    # Record the current time so we can figure out how long it took us to
    # do all this scanning.
    logger.configure(DEFAULT_LOG_VERBOSITY, logger.LoggingMode.COMMAND)
    interfaces = get_all_interfaces_definition(annotate_with_monitored=False)
    if args.verbose:
        print("Interface dictionary:\n%s" % pformat(interfaces), file=stdout)
    protocol = do_beaconing(args, interfaces=interfaces)
    if args.verbose:
        print("Transmit queue:\n%s" % pformat(protocol.tx_queue), file=stdout)
        print("Receive queue:\n%s" % pformat(protocol.rx_queue), file=stdout)
        print(
            "Topology hints:\n%s" % pformat(protocol.topology_hints),
            file=stdout,
        )
