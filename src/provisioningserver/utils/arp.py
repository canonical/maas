# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with ARP packets."""

import os
import subprocess
import sys
from textwrap import dedent

from provisioningserver.path import get_path
from provisioningserver.utils import sudo
from provisioningserver.utils.script import ActionScriptError


def add_arguments(parser):
    """Add this command's options to the `ArgumentParser`.

    Specified by the `ActionScript` interface.
    """
    parser.description = dedent(
        """\
        Observes the traffic on the specified interface, looking for ARP
        traffic. Outputs JSON objects (one per line) for each NEW, REFRESHED,
        or MOVED binding.

        Reports on REFRESHED bindings at most once every ten minutes.
        """
    )
    parser.add_argument(
        "interface",
        type=str,
        nargs="?",
        help="Ethernet interface from which to capture traffic. Optional if "
        "an input file is specified.",
    )


def run(args, output=sys.stdout):
    """Observe an Ethernet interface and print ARP bindings."""

    # First, become a progress group leader, so that signals can be directed
    # to this process and its children; see p.u.twisted.terminateProcess.
    os.setpgrp()

    network_monitor = None
    if args.interface is None:
        raise ActionScriptError("Required argument: interface")

    cmd = [get_path("/usr/sbin/maas-netmon"), args.interface]
    cmd = sudo(cmd)
    network_monitor = subprocess.Popen(cmd, stdout=output)
    if network_monitor is not None:
        return_code = network_monitor.poll()
        if return_code is not None:
            raise SystemExit(return_code)
