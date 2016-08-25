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

__all__ = [
    "add_arguments",
    "run",
    "observe_mdns",
    "parse_avahi_event",
    "unescape_avahi_service_name",
]

import io
import json
import os
import re
import stat
import subprocess
import sys
from textwrap import dedent
import time

from provisioningserver.utils.script import ActionScriptError


def _rstrip(s: str, suffix: str) -> str:
    """Strips the specified suffix from the end of the string, if it exists."""
    if s.endswith(suffix):
        return s[:-len(suffix)]
    return s


def unescape_avahi_service_name(string: str) -> str:
    """Make an avahi service name human-readable."""
    # See the avahi escape algorithm here:
    # https://paste.ubuntu.com/23083868/
    # Escapes "\" and "." with "\\" and "\.", respectively.
    # Then, finds occurrences of '\\nnn' and convert them to chr(nnn).
    # (The escape algorithm leaves alone characters in the set [a-zA-Z_-].)
    regex = r'(?P<int>\\\d\d\d)|(?P<dot>\\\.)|(?P<slash>\\\\)'

    def unescape_avahi_token(token: str):
        """Replace the appropriately-matched regex group with the unescaped
        version of the string.
        """
        if token.group('int') is not None:
            return chr(int(token.group('int')[2:]))
        if token.group('dot') is not None:
            return '.'
        elif token.group('slash') is not None:
            return '\\'
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
    fields = line.rstrip().split(';', 9)
    if len(fields) < 6:
        return None
    event_type = fields[0]
    # The type of the event is indicated in the first character from
    # avahi-browse. The following fields (no matter the event type) will
    # always be interface, protocol, label, type, and domain.
    data['interface'] = fields[1]
    data['protocol'] = fields[2]
    data['service_name'] = unescape_avahi_service_name(fields[3])
    data['type'] = fields[4]
    data['domain'] = fields[5]
    if event_type == '+':
        # An avahi service was added.
        data['event'] = 'BROWSER_NEW'
    elif event_type == '=':
        # An avahi service was resolved. This is really what we care about,
        # since it's what contains the interesting data.
        data['event'] = 'RESOLVER_FOUND'
        # For convenience, include both the FQDN and the plain hostname.
        domain = '.' + fields[5]
        data['fqdn'] = fields[6]
        data['hostname'] = _rstrip(fields[6], domain)
        data['address'] = fields[7]
        data['port'] = fields[8]
        data['txt'] = fields[9]
    elif event_type == '-':
        # An avahi service was removed.
        data['event'] = 'BROWSER_REMOVED'
    return data


def observe_mdns(verbose=False, input=sys.stdin, output=sys.stdout):
    """Function for printing avahi hostname bindings on stdout.
    """
    seen = dict()
    for line in input:
        event = parse_avahi_event(line)
        if event is None:
            continue
        if verbose is True:
            output.write(json.dumps(event))
            output.write("\n")
            output.flush()
        elif event['event'] == 'RESOLVER_FOUND':
            # In non-verbose mode, we only care about the critical data.
            interface = event['interface']
            hostname = event['hostname']
            address = event['address']
            entry = (address, hostname, interface)
            # Use a monotonic clock to protect ourselves from clock skew.
            clock = int(time.monotonic())
            # Check if we've seen this mDNS entry in the past ten minutes.
            if entry in seen and clock <= (seen[entry] + 600):
                continue
            else:
                # If we haven't seen this entry [recently], update its
                # last-seen time and continue to report it.
                seen[entry] = clock
            data = {
                'interface': interface,
                'hostname': hostname,
                'address': address,
            }
            output.write(json.dumps(data))
            output.write("\n")
            output.flush()


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent("""\
        Uses the `avahi-browse` utility to observe mDNS activity on the
        network.

        Outputs JSON objects (one per line) for each event that occurs.
        """)
    parser.add_argument(
        '-v', '--verbose', action='store_true', required=False,
        help='Dumps all data gathered from `avahi-browse`. Defaults is to '
             'dump only data relevant to MAAS.')
    parser.add_argument(
        '-i', '--input-file', type=str, required=False,
        help="File to read avahi-browse output from. Use - for stdin. Default "
             "is to call `/usr/bin/avahi-browse` to get input.")


def run(args, output=sys.stdout, stdin=sys.stdin):
    """Observe an Ethernet interface and print ARP bindings."""
    avahi_browse = None
    if args.input_file is None:
        avahi_browse = subprocess.Popen(
            ["/usr/bin/avahi-browse", "--all", "--resolve", "--no-db-lookup",
             "--parsable", "--no-fail"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        infile = io.TextIOWrapper(avahi_browse.stdout, encoding='utf-8')
    else:
        if args.input_file == '-':
            mode = os.fstat(stdin.fileno()).st_mode
            if not stat.S_ISFIFO(mode):
                raise ActionScriptError("Expected stdin to be a pipe.")
            infile = stdin
        else:
            infile = open(args.input_file, "r")
    observe_mdns(
        input=infile, output=output, verbose=args.verbose)
    if avahi_browse is not None:
        return_code = avahi_browse.poll()
        if return_code is not None:
            raise SystemExit(return_code)
