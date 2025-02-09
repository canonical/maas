# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with avahi.

Requires the `avahi-utils` package.

Note that `avahi-browse` does not seem to return data with consistent address
families. In order to gather complete information, one could use the data from
`avahi-browse` in conjunction with `avahi-resolve`. For example, if a hostname
of `foo.local` is discovered with `avahi-browse`, the following commands could
be used to resolve it:

$ avahi-resolve -6 -n foo.local
foo.local fe80::95de:80ff:fe6a:cb54

$ avahi-resolve -4 -n foo.local
foo.local 192.168.0.155

However, `avahi-resolve` does not allow interface selection, so it is still
possible that the result could be incorrect.

The mDNS RFC (RFC 6762) provides a clue about why this might be in its "IPv6
Considerations" section[1]. mDNS has the concept of "two separate .local
domains", one of which can be seen by IPv4-only hosts, the other which can
be seen by IPv6-only hosts. Dual-stack hosts can see both. When a dual stack
host resolves a service using mDNS, it may prefer one address family over
another.

[1]: https://tools.ietf.org/html/rfc6762#section-20
"""

from contextlib import contextmanager
import io
import json
import os
import re
import subprocess
import sys
from textwrap import dedent
import time
from typing import Iterable

from provisioningserver.path import get_path


def _rstrip(s: str, suffix: str) -> str:
    """Strips the specified suffix from the end of the string, if it exists."""
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def unescape_avahi_service_name(string: str) -> str:
    """Make an avahi service name human-readable."""
    # See the avahi escape algorithm here:
    # https://paste.ubuntu.com/23083868/
    # Escapes "\" and "." with "\\" and "\.", respectively.
    # Then, finds occurrences of '\\nnn' and convert them to chr(nnn).
    # (The escape algorithm leaves alone characters in the set [a-zA-Z_-].)
    regex = r"(?P<int>\\\d\d\d)|(?P<dot>\\\.)|(?P<slash>\\\\)"

    def unescape_avahi_token(token: str):
        """Replace the appropriately-matched regex group with the unescaped
        version of the string.
        """
        if token.group("int") is not None:
            return chr(int(token.group("int")[2:]))
        if token.group("dot") is not None:
            return "."
        elif token.group("slash") is not None:
            return "\\"

    return re.sub(regex, unescape_avahi_token, string)


def parse_avahi_event(line: str) -> dict:
    """Parses a line of output from `avahi-browse --parsable`."""
    # While there seems to be no official specification for the format of
    # `avahi-browse` output, given that --parsable is an option, it is assumed
    # that this is a stable enough interface to use. The following Python code
    # was cross-checked with the avahi source code. To be specific,
    # avahi-utils/avahi-browse.c was consulted to ensure compatibility (and
    # consistency with the event names used in the avahi code).
    data = {}
    # Limit to 9 fields here in case a ';' appears in the TXT record unescaped.
    fields = line.rstrip().split(b";", 9)
    if len(fields) < 6:
        return None
    for index, field in enumerate(fields):
        # the 9th field is TXT, which can contain anything, including
        # binary characters. There's a bug about this, that maybe
        # avahi-browser should escape those binary characters, which
        # would allow us to treat everything as utf-8:
        # https://github.com/lathiat/avahi/issues/169
        if index != 9:
            fields[index] = field.decode("utf-8")
    event_type = fields[0]
    # The type of the event is indicated in the first character from
    # avahi-browse. The following fields (no matter the event type) will
    # always be interface, protocol, label, type, and domain.
    data["interface"] = fields[1]
    data["protocol"] = fields[2]
    data["service_name"] = unescape_avahi_service_name(fields[3])
    data["type"] = fields[4]
    data["domain"] = fields[5]
    if event_type == "+":
        # An avahi service was added.
        data["event"] = "BROWSER_NEW"
    elif event_type == "=":
        # An avahi service was resolved. This is really what we care about,
        # since it's what contains the interesting data.
        data["event"] = "RESOLVER_FOUND"
        # For convenience, include both the FQDN and the plain hostname.
        domain = "." + fields[5]
        data["fqdn"] = fields[6]
        data["hostname"] = _rstrip(fields[6], domain)
        data["address"] = fields[7]
        data["port"] = fields[8]
        data["txt"] = fields[9]
    elif event_type == "-":
        # An avahi service was removed.
        data["event"] = "BROWSER_REMOVED"
    return data


def _extract_mdns_events(lines: Iterable[str]) -> Iterable[dict]:
    """Extract Avahi-format mDNS events from the given stream."""
    for event in map(parse_avahi_event, lines):
        if event is not None:
            yield event


def _observe_mdns(reader, output: io.TextIOBase, verbose: bool):
    """Process the given `reader` for `avahi-browse` events.

    IO is mostly isolated in this function; the transformation functions
    `_observe_all_in_full` and `_observe_resolver_found` can be tested without
    having to deal with IO.

    :param reader: A context-manager yielding a `io.TextIOBase`.
    """
    if verbose:
        observer = _observe_all_in_full
    else:
        observer = _observe_resolver_found
    with reader as infile:
        events = _extract_mdns_events(infile)
        for event in observer(events):
            print(json.dumps(event), file=output, flush=True)


def _observe_all_in_full(events: Iterable[dict]) -> Iterable[dict]:
    """Report on all mDNS events, in full."""
    return iter(events)


def _observe_resolver_found(events: Iterable[dict]) -> Iterable[dict]:
    """Report on `RESOLVER_FOUND` events only, with restricted details.

    The RESOLVER_FOUND event is interesting to MAAS right now; other events
    like BROWSER_NEW and BROWSER_REMOVED are not.
    """
    seen = dict()
    for event in filter(_p_resolver_found, events):
        # In non-verbose mode we only care about the critical data.
        interface = event["interface"]
        hostname = event["hostname"]
        address = event["address"]
        entry = (address, hostname, interface)
        # Use a monotonic clock to protect ourselves from clock skew.
        clock = int(time.monotonic())
        # Check if we've seen this mDNS entry in the past ten minutes.
        if entry not in seen or clock > (seen[entry] + 600):
            # We haven't seen this entry [recently], so update its
            # last-seen time and report it.
            seen[entry] = clock
            yield {
                "interface": interface,
                "hostname": hostname,
                "address": address,
            }


def _p_resolver_found(event):
    """Return `True` if this is a `RESOLVER_FOUND` event."""
    return event["event"] == "RESOLVER_FOUND"


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Uses the `avahi-browse` utility to observe mDNS activity on the
        network.

        Outputs JSON objects (one per line) for each event that occurs.
        """
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        required=False,
        help="Dumps all data gathered from `avahi-browse`. Defaults is to "
        "dump only data relevant to MAAS.",
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=str,
        required=False,
        help="File to read avahi-browse output from. Use - for stdin. Default "
        "is to call `/usr/bin/avahi-browse` to get input.",
    )


def run(args, output=sys.stdout, stdin=sys.stdin):
    """Observe an Ethernet interface and print ARP bindings."""

    # First, become a progress group leader, so that signals can be directed
    # to this process and its children; see p.u.twisted.terminateProcess.
    os.setpgrp()

    if args.input_file is None:
        reader = _reader_from_avahi()
    elif args.input_file == "-":
        reader = _reader_from_stdin(stdin)
    else:
        reader = _reader_from_file(args.input_file)
    try:
        _observe_mdns(reader, output, args.verbose)
    except KeyboardInterrupt:
        # Suppress this exception and allow for a clean exit instead.
        # ActionScript would exit 1 if we allowed it to propagate, but
        # SIGINT/SIGTERM are how this script is meant to be terminated.
        pass


@contextmanager
def _reader_from_avahi():
    """Read from a newly spawned `avahi-browse` subprocess.

    :raises SystemExit: If `avahi-browse` exits non-zero.
    """
    avahi_browse = subprocess.Popen(
        [
            get_path("/usr/bin/avahi-browse"),
            "--all",
            "--resolve",
            "--no-db-lookup",
            "--parsable",
            "--no-fail",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )
    try:
        # Avahi says "All strings used in DNS-SD are UTF-8 strings".
        yield avahi_browse.stdout
    finally:
        # SIGINT or SIGTERM (see ActionScript.setup) has been received,
        # avahi-browse may have crashed or been terminated, or there may have
        # been an exception in this script. In any case we give the subprocess
        # a chance to exit cleanly if it has not done so already, and then we
        # report on that exit.
        if _terminate_process(avahi_browse) != 0:
            raise SystemExit(avahi_browse.returncode)


@contextmanager
def _reader_from_stdin(stdin):
    """Reader from `stdin`.

    Using `sys.stdin` as a context manager directly would cause it to be
    closed on exit from the context, but that's not necessarily what we want;
    we may exit the context because of an error, not because stdin has been
    exhausted, so we want to insulate it from that.
    """
    yield stdin


@contextmanager
def _reader_from_file(filename):
    """Reader from `filename`."""
    # Avahi says "All strings used in DNS-SD are UTF-8 strings".
    with open(filename, "rb") as infile:
        yield infile


def _terminate_process(process, wait=2.5, kill=2.5):
    """Ensures that `process` terminates.

    :return: The exit code of the process.
    """
    try:
        # The subprocess may have already been signalled, for example as part
        # of this process's process group when Ctrl-c is pressed at the
        # terminal, so give it some time to exit.
        return process.wait(timeout=wait)
    except subprocess.TimeoutExpired:
        # Either the subprocess has not been signalled, or it's slow.
        process.terminate()  # SIGTERM.
        try:
            return process.wait(timeout=kill)
        except subprocess.TimeoutExpired:
            process.kill()  # SIGKILL.
            return process.wait()
