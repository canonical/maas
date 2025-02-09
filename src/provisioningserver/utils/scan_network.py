# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for scanning attached networks."""

from collections import namedtuple
import json
from multiprocessing import cpu_count
from multiprocessing.pool import ThreadPool
import os
import subprocess
import sys
from textwrap import dedent
import time

from netaddr import IPNetwork, IPSet
from netaddr.core import AddrFormatError

from provisioningserver.utils import sudo
from provisioningserver.utils.network import get_all_interfaces_definition
from provisioningserver.utils.script import ActionScriptError
from provisioningserver.utils.shell import (
    get_env_with_locale,
    has_command_available,
)

PingParameters = namedtuple("PingParameters", ("interface", "ip"))


NmapParameters = namedtuple("NmapParameters", ("interface", "cidr", "slow"))


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Generate traffic which attempts to confirm the existence of
        neighbours on specified CIDRs and/or interfaces.

        This command is intended to be used in conjunction with the network
        discovery feature in MAAS. It attempts to send the minimum possible
        amount of traffic in order for network discovery to recognize hosts.

        If no arguments are provided, checks all IPv4 addresses on all
        configured CIDRs on each interface.

        If nmap is not installed, this command could take a very long time if
        there are a large amount of hosts connected directly to any attached
        networks.

        This command only considers IPv4 CIDRs. (IPv6 CIDRs are excluded.)
        """
    )
    parser.add_argument(
        "-s",
        "--slow",
        action="store_true",
        required=False,
        help="Scan slower. Only applies to nmap scans; ping is slow already.",
    )
    parser.add_argument(
        "-t",
        "--threads",
        required=False,
        type=int,
        help="Number of concurrent threads to spawn during a scan. "
        "Default is to spawn four times the number of CPUs when using "
        "ping, or one times the number of CPUs when using nmap.",
    )
    parser.add_argument(
        "-p",
        "--ping",
        action="store_true",
        required=False,
        help="Scan using ping. (Default is to scan with nmap, if installed.)",
    )
    parser.add_argument(
        "interface",
        type=str,
        nargs="?",
        help="Ethernet interface to ping from. Optional if all interfaces are "
        "to be considered. If an interface is not specified, the first "
        "argument will be treated as a CIDR, and each interface "
        "configured on matching CIDRs (or configured with a CIDR that is "
        "a superset of a specified CIDR) will be scanned.",
    )
    parser.add_argument(
        "cidr",
        type=str,
        nargs="*",
        help="CIDR(s) to scan. Default is to scan all configured CIDRs. If an "
        "interface is specified, restricts the scan to that interface, "
        "and scans the CIDR(s) even if it is not configured. If an "
        "interface is specified, but no CIDR(s) are specified, scans "
        "any configured CIDR on that interface.",
    )


def yield_ipv4_networks_on_link(ifname: str, interfaces: dict):
    """Yields each IPv4 CIDR on the specified interface.

    :param ifname: the name of the interface whose CIDRs to yield.
    :param interfaces: the output of `get_all_interfaces_definition()`.
    """
    return [
        link["address"]
        for link in interfaces[ifname]["links"]
        if IPNetwork(link["address"]).version == 4
    ]


def yield_cidrs_on_interface(cidr_set: IPSet, ifname: str, interfaces: dict):
    """Yields each CIDR in the `cidr_set` configured on `ifname`.

    Also yields each CIDR which is a subset of a configured CIDR.
    """
    network_set = IPSet(yield_ipv4_networks_on_link(ifname, interfaces))
    for cidr in (cidr_set & network_set).iter_cidrs():
        yield str(cidr)


def get_interface_cidrs_to_scan(
    interface_name: str, cidrs: list, interfaces: dict
) -> dict:
    """Returns a dictionary of {<interface-name>: <iterable-of-cidr-strings>}.

    Given the specified `interface_name` (which can be None, which means
    to scan all interfaces) and the given list of CIDRs (which can be empty),
    return a dictionary of which interfaces to scan, and which CIDRs to
    scan on those interfaces.

    :return: dict of {<interface-name>: <iterable-of-cidr-strings>}.
    """
    if interface_name is None:
        if len(cidrs) == 0:
            # No interface specified, so scan all CIDRs on all interfaces.
            to_scan = {
                ifname: yield_ipv4_networks_on_link(ifname, interfaces)
                for ifname in interfaces
            }
        else:
            # No interface name supplied, but CIDRs were supplied. Scan
            # (interface, cidr) pairs with matching CIDRs, and/or CIDRs which
            # are a superset of the specified CIDRs.
            to_scan = {
                ifname: list(
                    yield_cidrs_on_interface(IPSet(cidrs), ifname, interfaces)
                )
                for ifname in interfaces
            }
    else:
        if len(cidrs) > 0:
            # The interface was specified, along with one or more CIDRs.
            to_scan = {interface_name: cidrs}
        else:
            # A specific interface was specified, but no specific CIDRs.
            # In this case, we scan any IPv4 CIDRs we find on that interface.
            to_scan = {
                interface_name: yield_ipv4_networks_on_link(
                    interface_name, interfaces
                )
            }
    return to_scan


def yield_ping_parameters(to_scan):
    """Yields each (interface, ip) pair to scan.

    :param to_scan: dict of {<interface-name>: <iterable-of-cidr-strings>}.
    """
    for interface in to_scan:
        for cidr in to_scan[interface]:
            ipnetwork = IPNetwork(cidr)
            if ipnetwork.version == 4:
                for ip in ipnetwork.iter_hosts():
                    yield PingParameters(interface, str(ip))


def yield_nmap_parameters(to_scan, slow):
    """Yields each IPv4 (interface, cidr) pair to scan.

    :param to_scan: dict of {<interface-name>: <iterable-of-cidr-strings>}.
    """
    for interface in to_scan:
        for cidr in to_scan[interface]:
            ipnetwork = IPNetwork(cidr)
            if ipnetwork.version == 4:
                yield NmapParameters(interface, str(ipnetwork.cidr), slow)


def get_nmap_arguments(args: NmapParameters):
    """Constructs a list of the appropriate arguments for running `nmap`.

    :param args: The `NmapParameters` namedtuple.
    :param args.interface: The interface to scan.
    :param args.cidr: The CIDR to scan.
    :param args.slow: If True, will throttle scanning to 9 packets per second.
    :return: list
    """
    nmap_args = sudo(["nmap", "-e", args.interface])
    if args.slow is True:
        # If we're doing a slow scan, use a packets-per-second limit.
        # A rate limit of 9 PPS tends to scan a /24 in about one minute.
        nmap_args.extend(["--max-rate", "9"])
    nmap_args.extend(
        [
            # Ping scan (disable port scan).
            "-sn",
            # Never do DNS resolution.
            "-n",
            # Output XML to stdout. (in case we want to parse it later.)
            "-oX",
            "-",
            # Ping scan type: neighbour discovery scan. (that is, ARP-only.)
            "-PR",
            args.cidr,
        ]
    )
    return nmap_args


def run_nmap(args: NmapParameters) -> dict:
    """Runs `nmap` to scan the target using the specified arguments.

    Note: This function is required to take a single parameter, due to the way
    Pool.imap(...) works.

    :param args: NmapParameters namedtuple
    :return: dict representing the event that occurred.
    """
    clock = time.monotonic()
    nmap = subprocess.Popen(
        get_nmap_arguments(args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=get_env_with_locale(),
        # This pre-exec function prevents `nmap` from writing to the pty, which
        # misbehaves when it runs in parallel and can require a `reset`.
        preexec_fn=os.setsid,
    )
    nmap.wait()
    clock_diff = time.monotonic() - clock
    event = {
        "scan_type": "nmap",
        "interface": args.interface,
        "cidr": args.cidr,
        "returncode": nmap.returncode,
        "seconds": int(clock_diff),
        "slow": args.slow,
    }
    return event


def nmap_scan(to_scan, slow=False, threads=None, threads_per_cpu=1):
    """Scans the specified networks using `nmap`.

    The `to_scan` dictionary must be in the format:

        {<interface-name>: <iterable-of-cidr-strings>, ...}

    If the `slow` option is specified, will limit the maximum rate nmap
    uses to send out packets.
    """
    jobs = yield_nmap_parameters(to_scan, slow)
    if threads is None:
        threads = cpu_count() * threads_per_cpu
    if threads == 1:
        yield from (run_nmap(job) for job in jobs)
    with ThreadPool(processes=threads) as pool:
        yield from pool.imap_unordered(run_nmap, jobs)


def get_ping_arguments(args: PingParameters):
    """Constructs a list of the appropriate arguments for running `ping`.

    :param interface: The interface to initiate the ping from.
    :param ip: The IPv4 address to ping.
    """
    return [
        "ping",
        # Bypass the routing table. (send directly on the given interface.)
        "-r",
        "-I",
        args.interface,
        args.ip,
        # Stop after 3 tries.
        "-c",
        "3",
        # Wait at most one second. This is the minimum that 'ping' accepts.
        # (less would be better)
        "-w",
        "1",
        # Send packets 0.2 seconds apart. (this is the minimum)
        "-i",
        "0.2",
        # Print the timestamp. (This is only used for debugging.)
        "-D",
        # Log outstanding replies before sending next packet.
        # (Only used for debugging.)
        "-O",
        # Numeric output only. (Don't resolve DNS.)
        "-n",
        # This reads: http://maas.io/ (in ASCII-encoded hex bytes).
        # This string will be sent repeatedly in each ping packet payload.
        "-p",
        "687474703a2f2f6d6161732e696f2f20",
    ]


def run_ping(args: PingParameters) -> dict:
    """Runs `ping` and returns the resulting event.

    Note: This function is required to take a single parameter, due to the way
    Pool.imap(...) works.

    :param args: PingParameters namedtuple
    :return: dict representing the event that occurred.
    """
    ping = subprocess.Popen(
        get_ping_arguments(args),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=get_env_with_locale(),
    )
    ping.wait()
    result = bool(ping.returncode == 0)
    event = {
        "scan_type": "ping",
        "interface": args.interface,
        "ip": args.ip,
        "result": result,
    }
    return event


def ping_scan(to_scan: dict, threads=None, threads_per_cpu=4):
    """Scans the specified networks using `ping`.

    The `to_scan` dictionary must be in the format:

        {<interface_name>: <iterable-of-cidr-strings>, ...}

    If the `threads` argument is supplied, the specified number of threads
    will be used for concurrent scanning. If threads=1 is specified, scanning
    will use a single process (and be very slow).
    """
    jobs = yield_ping_parameters(to_scan)
    if threads is None:
        threads = cpu_count() * threads_per_cpu
    if threads == 1:
        yield from (run_ping(job) for job in jobs)
    else:
        with ThreadPool(processes=threads) as pool:
            yield from pool.imap(run_ping, jobs)


def write_event(event, output=sys.stdout):
    """Writes an event dictionary to the specified stream in JSON format.

    Defaults to writing to stdout.
    """
    output.write(json.dumps(event))
    output.write("\n")
    output.flush()


def warn_about_missing_cidrs(
    ifname_to_scan: str, cidrs: list, interfaces: dict, stderr: object
):
    """Write a warning to the specified `stderr` stream if `ifname_to_scan`
    is not configured with `cidrs`."""
    cidrs_on_interface = {
        IPNetwork(cidr)
        for cidr in yield_ipv4_networks_on_link(ifname_to_scan, interfaces)
    }
    for cidr in cidrs:
        if IPNetwork(cidr) not in cidrs_on_interface:
            stderr.write(
                f"Warning: {cidr} is not present on {ifname_to_scan}\n"
            )
            stderr.flush()


def validate_ipv4_cidrs(cidrs):
    """Validates that each item in the specified iterable is an IPv4 CIDR.

    :raise ActionScriptError: if one or more item is not an IPv4 CIDR.
    """
    for cidr in cidrs:
        try:
            IPNetwork(cidr, version=4)
        except AddrFormatError:
            raise ActionScriptError("Not a valid IPv4 CIDR: %s" % cidr)  # noqa: B904


def adjust_scanning_parameters(
    ifname_to_scan: str, cidrs: list, interfaces: dict
) -> str:
    """Adjust scan settings `ifname_to_scan` is not an interface name.

    If the first argument was a CIDR instead of an interface, add it to the
    list of CIDRs and return the (possibly modified) `ifname_to_scan`.

    :raise ActionScriptError: If the `ifname_to_scan` (the first positional
        argument specified) is neither an interface name nor a CIDR.
    """
    if ifname_to_scan is not None and ifname_to_scan not in interfaces:
        if "/" in ifname_to_scan:
            cidrs.append(ifname_to_scan)
        else:
            raise ActionScriptError(
                "First argument must be an interface or CIDR: %s"
                % ifname_to_scan
            )
        ifname_to_scan = None
    return ifname_to_scan


def scan_networks(args, to_scan, stderr, stdout):
    """Interprets the specified `args` and `to_scan` dict to perform the scan.

    Uses the specified `stdout` and `stderr` for output.
    """
    # Start the clock. (We want to measure how long the scan takes.)
    clock = time.monotonic()
    # The user must explicitly opt out of using `nmap` by selecting --ping,
    # unless `nmap` is not installed.
    use_nmap = has_command_available("nmap")
    use_ping = args.ping
    if use_nmap and not use_ping:
        tool = "nmap"
        scanner = nmap_scan(to_scan, slow=args.slow, threads=args.threads)
        count = 0
        for count, event in enumerate(scanner, 1):  # noqa: B007
            write_event(event, stdout)
        clock_diff = time.monotonic() - clock
        if count > 0:
            stderr.write(
                "%d nmap scan(s) completed in %d second(s).\n"
                % (count, clock_diff)
            )
            stderr.flush()
    else:
        tool = "ping"
        # For a ping scan, we can easily get a count of the number of hosts,
        # and whether or not the ping was successful. It will be printed to
        # stderr for informational purposes.
        count = 0
        hosts = 0
        for event in ping_scan(to_scan, threads=args.threads):
            count += 1
            if event["result"] is True:
                hosts += 1
            write_event(event, stdout)
        clock_diff = time.monotonic() - clock
        if count > 0:
            stderr.write(
                "Pinged %d hosts (%d up) in %d second(s).\n"
                % (count, hosts, clock_diff)
            )
            stderr.flush()
    return {"count": count, "tool": tool, "seconds": clock_diff}


def run(args, stdout=sys.stdout, stderr=sys.stderr):
    """Scan local networks for on-link hosts.

    :param args: Parsed output of the arguments added in `add_arguments()`.
    :param stdout: Standard output stream to write to.
    :param stderr: Standard error stream to write to.
    """
    # Record the current time so we can figure out how long it took us to
    # do all this scanning.
    ifname_to_scan = args.interface
    cidrs = args.cidr

    # We'll need this data to determine which interfaces we can scan.
    interfaces = get_all_interfaces_definition(annotate_with_monitored=False)

    # We may need to adjust the scanning parameters if the first positional
    # argument was a CIDR and not an interface.
    ifname_to_scan = adjust_scanning_parameters(
        ifname_to_scan, cidrs, interfaces
    )

    # Validate that each CIDR is an IPv4 CIDR. We don't want to spend an
    # eternity trying to scan an IPv6 subnet.
    validate_ipv4_cidrs(cidrs)

    # Get the dictionary of {interfaces: cidrs} to scan.
    to_scan = get_interface_cidrs_to_scan(ifname_to_scan, cidrs, interfaces)

    # Validate that `to_scan` looks sane.
    if ifname_to_scan is not None:
        # This means we're only scanning one interface, so we should warn the
        # user if they requested to scan a CIDR that doesn't exist.
        warn_about_missing_cidrs(ifname_to_scan, cidrs, interfaces, stderr)

    result = scan_networks(args, to_scan, stderr, stdout)
    if result["count"] == 0:
        stderr.write(
            "Requested network(s) not available to scan: %s\n"
            % (", ".join(cidrs) if len(cidrs) > 0 else ifname_to_scan)
        )
        stderr.flush()
