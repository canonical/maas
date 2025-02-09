# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for inspecting dhclient."""

import os
import re

from provisioningserver.utils.fs import read_text_file
from provisioningserver.utils.ps import get_running_pids_with_command

re_entry = re.compile(
    r"""
    ^\s*              # Ignore leading whitespace on each line.
    lease             # Look only lease stanzas.
    \s+{              # Open bracket.
    ([^}]+)           # Capture the contents of lease.
    }                 # Close bracket.
    """,
    re.MULTILINE | re.DOTALL | re.VERBOSE,
)


def get_lastest_fixed_address(lease_path):
    """Return the lastest fixed address assigned in `lease_path`."""
    try:
        lease_contents = read_text_file(lease_path)
    except FileNotFoundError:
        return None

    matches = re_entry.findall(lease_contents)
    if len(matches) > 0:
        # Get the IP address assigned to the interface.
        last_lease = matches[-1]
        for line in last_lease.splitlines():
            line = line.strip()
            if len(line) > 0:
                statement, value = line.split(" ", 1)
                if statement in ["fixed-address", "fixed-address6"]:
                    return value.split(";", 1)[0].strip()
    # No matches or unable to identify fixed-address{6} in the last match.
    return None


def get_dhclient_info(proc_path="/proc"):
    """Return dictionary mapping interfaces to assigned address from
    dhclient.
    """
    dhclient_pids = get_running_pids_with_command(
        "dhclient", proc_path=proc_path
    )
    dhclient_info = {}
    for pid in dhclient_pids:
        cmdline = read_text_file(
            os.path.join(proc_path, str(pid), "cmdline")
        ).split("\x00")
        if "-lf" in cmdline:
            idx_lf = cmdline.index("-lf")
            lease_path = cmdline[idx_lf + 1]  # After '-lf' option.
            interface_name = cmdline[-2]  # Last argument.
            ip_address = get_lastest_fixed_address(lease_path)
            if (
                ip_address is not None
                and len(ip_address) > 0
                and not ip_address.isspace()
            ):
                dhclient_info[interface_name] = ip_address
    return dhclient_info
