#!/bin/bash -e
#
# internet_connectivity - Check if the system has access to the Internet.
#
# Author: Lee Trager <lee.trager@canonical.com>
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

# Download the index.sjson file used by MAAS to download images to validate
# internet connectivity.
#
# --- Start MAAS 1.0 script metadata ---
# name: internet-connectivity
# title: Network validation
# description: Check if the system has access to the Internet.
# tags: [network, internet]
# script_type: test
# parallel: any
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata ---

URL="https://images.maas.io/ephemeral-v3/daily/streams/v1/index.sjson"
echo "Attempting to retrieve: $URL"
curl -ILSsv -A maas_internet_connectivity_test $URL
