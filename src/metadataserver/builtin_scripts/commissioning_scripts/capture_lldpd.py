#!/usr/bin/env python3
#
# maas-capture-lldpd - Capture lldpd output
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
# name: maas-capture-lldpd
# title: Capture lldpd output
# description: Capture lldp output
# script_type: commissioning
# parallel: any
# timeout: 60
# --- End MAAS 1.0 script metadata ---

from os.path import getmtime
from subprocess import check_call
from time import sleep, time


def lldpd_capture(reference_file, time_delay):
    """Wait until `lldpd` has been running for `time_delay` seconds.

    On an Ubuntu system, `reference_file` is typically `lldpd`'s UNIX
    socket in `/var/run`. After waiting capture any output.
    """
    time_ref = getmtime(reference_file)
    time_remaining = time_ref + time_delay - time()
    if time_remaining > 0:
        # LP:1801152 - If the hardware clock is in the future when
        # 00-maas-03-install-lldpd runs and NTP corrects the clock
        # before this script runs time_remaining will be more then
        # the time_delay which may cause this script to timeout.
        sleep(min(time_remaining, time_delay))
    check_call(("lldpctl", "-f", "xml"))


if __name__ == "__main__":
    lldpd_capture("/var/run/lldpd.socket", 60)
