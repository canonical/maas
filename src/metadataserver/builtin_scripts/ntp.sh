#!/bin/bash -e
#
# ntp - Run ntp clock set to verify NTP connectivity.
#
# Author: Michael Iatrou <michael.iatrou (at) canonical.com>
#         Lee Trager <lee.trager (at) canonical.com>
#
# Copyright (C) 2017-2019 Canonical
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

# cloud-init configures ntp to use the rack controller or a user configured
# external ntp server before running the test scripts. This test ensures that
# the configured NTP server is accessible.
#
# --- Start MAAS 1.0 script metadata ---
# name: ntp
# title: NTP validation
# description: Run ntp clock set to verify NTP connectivity.
# tags: ntp
# script_type: test
# hardware_type: network
# parallel: any
# timeout: 00:01:00
# --- End MAAS 1.0 script metadata ---

function has_bin() {
    which $1 >/dev/null
    echo $?
}

if [ $(has_bin ntpd) -eq 0 ]; then
    echo -en 'INFO: ntpd detected.\n\n' 1>&2
    ntpq -np
    sudo -n systemctl stop ntp.service
    sudo -n timeout 10 ntpd -gq
    ret=$?
    sudo -n systemctl start ntp.service
elif [ $(has_bin chronyc) -eq 0 ]; then
    echo -en 'INFO: chrony detected.\n\n' 1>&2
    chronyc status
    chronyc sources
elif [ $(has_bin timedatectl) -eq 0 ]; then
    echo -en 'INFO: timesyncd detected.\n\n' 1>&2
    timedatectl status
    sudo -n systemctl status systemd-timesyncd.service
else
    echo -en 'ERROR: Unable to detect NTP service!\n\n' 1>&2
    exit 1
fi
