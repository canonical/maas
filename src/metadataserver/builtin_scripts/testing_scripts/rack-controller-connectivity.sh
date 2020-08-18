#!/bin/bash
#
# rack-controller-connectivity - Check if an interface has access to the booted rack controller.
#
# Author: Lee Trager <lee.trager@canonical.com>
#
# Copyright (C) 2019 Canonical
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
# name: rack-controller-connectivity
# title: Gateway Connectivity Validation
# description: Check if an interface has access to the booted rack controller.
# tags:
#   - network-validation
# script_type: test
# hardware_type: network
# parallel: instance
# parameters:
#   interface:
#     type: interface
# apply_configured_networking: True
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata ---

{{inject_file}}

OPTS=$(getopt -o 'i:h' --long 'interface:,help' -n 'rack-controller-connectivity' -- "$@")

if [ $? -ne 0 ]; then
    exit 1
fi

eval set -- "$OPTS"
unset OPTS

while true; do
    case "$1" in
        '-i'|'--interface')
            INTERFACE=$2
            shift 2
            continue
            ;;
        '-h'|'--help')
            echo "usage: rack-controller-connectivity [--interface INTERFACE]"
            echo
            echo "Check if an interface has access to the booted rack controller."
            echo
            echo "optional arguments:"
            echo "  -h, --help         Show this message"
            echo "  -i, --interface    The interface to test rack controller connectivity with."
            echo "                     Default: Any interface"
            exit 0
            ;;
        '--')
            shift
            break
            ;;
        *)
            echo "Unknown argument $1!" >&2
            exit 1
    esac
done

# When booting into the ephemeral environment root is the retrieved from
# the rack controller.
for i in $(cat /proc/cmdline); do
    arg=$(echo $i | cut -d '=' -f1)
    if [ "$arg" == "root" ]; then
        value=$(echo $i | cut -d '=' -f2-)
        # MAAS normally specifies the file has "filetype:url"
        filetype=$(echo $value | cut -d ':' -f1)
        if [ "$filetype" == "squash" ]; then
            url=$(echo $value | cut -d ':' -f2-)
        else
            url=$filetype
        fi
        break
    fi
done

if [ -z "$url" ] || $(echo "$url" | grep -vq "://"); then
    echo "ERROR: Unable to find rack controller URL!"
    exit 1
fi

test_interface "$INTERFACE" "$url"
