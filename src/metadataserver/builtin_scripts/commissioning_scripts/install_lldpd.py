#!/usr/bin/env python3
#
# 20-maas-01-install-lldpd - Install and configure lldpd for passive capture.
#
# Copyright (C) 2012-2020 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# --- Start MAAS 1.0 script metadata ---
# name: 20-maas-01-install-lldpd
# title: Install and configure lldpd for passive capture.
# description: Install and configure lldpd for passive capture.
# script_type: commissioning
# packages: {apt: lldpd}
# timeout: 30
# --- End MAAS 1.0 script metadata ---

from codecs import open
import os
from subprocess import check_call


def lldpd_install(config_file):
    """Installs and configures `lldpd` for passive capture.

    `config_file` refers to a shell script that is sourced by
    `lldpd`'s init script, i.e. it's Upstart config on Ubuntu.

    It selects the following options for the `lldpd` daemon:

    -c  Enable the support of CDP protocol to deal with Cisco routers
        that do not speak LLDP. If repeated, CDPv1 packets will be
        sent even when there is no CDP peer detected.

    -f  Enable the support of FDP protocol to deal with Foundry routers
        that do not speak LLDP. If repeated, FDP packets will be sent
        even when there is no FDP peer detected.

    -s  Enable the support of SONMP protocol to deal with Nortel
        routers and switches that do not speak LLDP. If repeated,
        SONMP packets will be sent even when there is no SONMP peer
        detected.

    -e  Enable the support of EDP protocol to deal with Extreme
        routers and switches that do not speak LLDP. If repeated, EDP
        packets will be sent even when there is no EDP peer detected.

    -r  Receive-only mode. With this switch, lldpd will not send any
        frame. It will only listen to neighbors.

    These flags are chosen so that we're able to capture information
    from a broad spectrum of equipment, but without advertising the
    node's temporary presence.

    """
    print("INFO: Configuring lldpd...")

    with open(config_file, "a", "ascii") as fd:
        fd.write("\n")  # Ensure there's a newline.
        fd.write("# Configured by MAAS:\n")
        fd.write('DAEMON_ARGS="-c -f -s -e -r"\n')

    print("INFO: Restarting lldpd...")
    check_call(("systemctl", "restart", "lldpd"))


def disable_embedded_lldp_agent_in_intel_cna_cards():
    """Intel cards that use i40e driver have an internal lldp processor
    on the NIC that filter out lldp packets before they can reach the
    host.  For the linux lldp daemon to receive such packets, we have to
    disable that feature.

    """
    addr_path = "/sys/kernel/debug/i40e"
    if not os.path.exists(addr_path):
        return
    for inner_dir in os.listdir(addr_path):
        command_path = f"{addr_path}/{inner_dir}/command"
        try:
            with open(command_path, "w", encoding="ascii") as command_file:
                command_file.write("lldp stop\n")
            print(f"INFO: Disabled embedded lldp agent for {inner_dir}")
        except OSError:
            print(
                "WARNING: Failed to disable the embedded lldp agent for {}".format(
                    inner_dir
                )
            )


if __name__ == "__main__":
    disable_embedded_lldp_agent_in_intel_cna_cards()
    lldpd_install("/etc/default/lldpd")
