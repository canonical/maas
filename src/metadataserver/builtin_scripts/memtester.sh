#!/bin/bash -ex
#
# memtester - Run memtester against all available userspace memory.
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
# name: memtester
# title: Memory integrity
# description: Run memtester against all available userspace memory.
# script_type: test
# hardware_type: memory
# packages: {apt: memtester}
# --- End MAAS 1.0 script metadata ---

# Memtester can only test memory free to userspace. At a minimum, reserve
# the min_free_kbytes + 10M or 0.77% of available memory, which ever is
# higher. This ensures the test doesn't fail due to the OOM killer. Only run
# memtester against available RAM once.

min_free_kbytes=$(cat /proc/sys/vm/min_free_kbytes)
reserve=$(awk '/MemTotal/ { print int(($2 * 0.0077)) }' /proc/meminfo)
if [ $reserve -le $min_free_kbytes ]; then
    reserve=$(($min_free_kbytes + 10240))
fi
testable_memory=$(awk -v reserve=$reserve '/MemFree/ { print int($2 - reserve) "K"}' /proc/meminfo)
sudo -n memtester $testable_memory 1
