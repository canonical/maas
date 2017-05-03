#!/bin/bash
#
# ntp - Run ntp clock set to verify NTP connectivity.
#
# Author: Michael Iatrou <michael.iatrou (at) canonical.com>
#
# Copyright (C) 2017 Canonical
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

source /etc/os-release

if [ $VERSION_ID == "14.04" ]; then
    which ntpq >/dev/null
    if [ $? -ne 0 ]; then
	echo -en 'Warning: NTP configuration is not supported in Trusty. ' 1>&2
	echo -en 'Running with the default NTP configuration.\n\n' 1>&2
	sudo -n apt-get install -q -y ntp
    fi
    ntpq -np
    sudo -n service ntp stop
    sudo -n timeout 10 ntpd -gq
    ret=$?
    sudo -n service ntp start
else
    ntpq -np
    sudo -n systemctl stop ntp.service
    sudo -n timeout 10 ntpd -gq
    ret=$?
    sudo -n systemctl start ntp.service
fi
exit $ret
