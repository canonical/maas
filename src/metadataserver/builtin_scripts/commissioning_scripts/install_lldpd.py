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
from codecs import open
from subprocess import check_call


def lldpd_install(config_file):
    print("INFO: Configuring lldpd...")

    with open(config_file, "a", "ascii") as fd:
        fd.write("\n")  # Ensure there's a newline.
        fd.write("# Configured by MAAS:\n")
        fd.write('DAEMON_ARGS="-c -f -s -e -r"\n')

    print("INFO: Restarting lldpd...")
    check_call(("systemctl", "restart", "lldpd"))


if __name__ == "__main__":
    lldpd_install("/etc/default/lldpd")
