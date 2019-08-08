#!/bin/bash
#
# gateway-connectivity - Check if an interface has access to the configured gateway.
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
# name: gateway-connectivity
# title: Gateway Connectivity Validation
# description: Check if an interface has access to the configured gateway.
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

OPTS=$(getopt -o 'i:h' --long 'interface:,help' -n 'gateway-connectivity' -- "$@")

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
            echo "usage: gateway-connectivity [--interface INTERFACE]"
            echo
            echo "Check if an interface has access to the configured gateway."
            echo
            echo "optional arguments:"
            echo "  -h, --help         Show this message"
            echo "  -i, --interface    The interface to test gateway connectivity with."
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


if [ -n "$INTERFACE" ]; then
    IP_ARGS="dev $INTERFACE"
fi

AWK_SCRIPT='
{
    for(i = 0; i < NF; i++) {
        if($i == "via") {
            print $(i + 1);
            break;
        }
    }
}
'

for gateway in $(ip route show $IP_ARGS | awk "$AWK_SCRIPT"); do
    if [ -n "$gateways" ]; then
        gateways="$gateways,$gateway"
    else
        gateways="$gateway"
    fi
done

for gateway in $(ip -6 route show $IP_ARGS | awk "$AWK_SCRIPT"); do
    if [ -n "$gateways" ]; then
        gateways="$gateways,$gateway"
    else
        gateways="$gateway"
    fi
done

if [ -z "$gateways" ]; then
    echo "WARNING: No gateways configured, skipping test"
    [ -n "$RESULT_PATH" ] && echo "{status: skipped}" >> $RESULT_PATH
    exit 0
fi

test_interface "$INTERFACE" "$gateways"
