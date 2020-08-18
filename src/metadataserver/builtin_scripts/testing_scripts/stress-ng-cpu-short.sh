#!/bin/bash -e
#
# stress-ng-cpu-short - Stress test the CPU for 5 minutes.
#
# Author: Lee Trager <lee.trager@canonical.com>
#
# Copyright (C) 2017-2018 Canonical
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
# name: stress-ng-cpu-short
# title: CPU validation
# description: Run stress-ng memory tests for 5 minutes.
# script_type: test
# hardware_type: cpu
# packages: {apt: stress-ng}
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata ---

sudo -n stress-ng --matrix 0 --ignite-cpu --log-brief --metrics-brief --times \
    --tz --verify --timeout 2m
echo
sudo -n stress-ng --cache 0 --ignite-cpu --log-brief --metrics-brief --times \
    --tz --verify --timeout 1m
echo
sudo -n stress-ng --cpu 0 --ignite-cpu --log-brief --metrics-brief --times --tz \
    --verify --timeout 2m
