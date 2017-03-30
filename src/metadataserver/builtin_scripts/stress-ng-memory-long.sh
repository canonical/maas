#!/bin/bash -e
#
# stress_ng_memory_long - Run stress-ng memory tests over 12 hours.
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

sudo -n apt-get install -q -y stress-ng
echo

# Reserve 64M so the test doesn't fail due to the OOM killer.
total_memory=$(awk '/MemAvailable/ { print ($2 - 65536) }' /proc/meminfo)
threads=$(lscpu --all --parse | grep -v '#' | wc -l)
memory_per_thread=$(($total_memory / $threads))
# stress-ng only allows 4GB of memory per thread.
if [ $memory_per_thread -ge 4194304 ]; then
    threads=$(($total_memory / 4194304 + 1))
    memory_per_thread=$(($total_memory / $threads))
fi

stress-ng --vm $threads --vm-bytes ${memory_per_thread}k --page-in \
    --log-brief --metrics-brief --times --tz --verify --timeout 12h
