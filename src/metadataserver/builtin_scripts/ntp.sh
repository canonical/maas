#!/bin/sh -e
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
e=0
ntpq -np
sudo systemctl stop ntp.service
sudo timeout 10 ntpd -gq || e=$?
sudo systemctl start ntp.service
exit $e
