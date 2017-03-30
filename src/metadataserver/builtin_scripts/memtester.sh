#!/bin/bash -e
#
# memtester - Run memtester against all available userspace memory.
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

sudo -n apt-get install -q -y memtester
echo

# Memtester can only test memory available to userspace. Reserve 32M so the
# test doesn't fail due to the OOM killer. Only run memtester against available
# RAM once.
sudo -n memtester \
     $(awk '/MemAvailable/ { print ($2 - 32768) "K"}' /proc/meminfo) 1
