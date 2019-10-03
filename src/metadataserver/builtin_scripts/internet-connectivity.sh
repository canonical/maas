#!/bin/bash
#
# internet-connectivity - Check if an interface can access the specified URL(s).
#
# Author: Lee Trager <lee.trager@canonical.com>
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
#
# --- Start MAAS 1.0 script metadata ---
# name: internet-connectivity
# title: Internet Connectivity Validation
# description: Check if an interface can access the specified URL(s).
# tags:
#   - internet
#   - network-validation
# script_type: test
# hardware_type: network
# parallel: instance
# parameters:
#   interface:
#     type: interface
#   url:
#     type: url
#     description: A comma seperated list of URLs, IPs, or domains to test if
#                  the specified interface has access to. Any protocol
#                  supported by curl is support. If no protocol or icmp is
#                  given the URL will be pinged.
#     default: https://connectivity-check.ubuntu.com
#     required: True
#     allow_list: True
# apply_configured_networking: True
# timeout: 00:05:00
# --- End MAAS 1.0 script metadata ---

{{inject_file}}

OPTS=$(getopt -o 'i:u:h' --long 'interface:,url:,help' -n 'internet-connectivity' -- "$@")

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
        '-u'|'--url')
            URL=$2
            shift 2
            continue
            ;;
        '-h'|'--help')
            echo "usage: internet-connectivity [--interface INTERFACE] [--url URL]"
            echo
            echo "Check if an interface can access the specified URL(s)."
            echo
            echo "optional arguments:"
            echo "  -h, --help         Show this message"
            echo "  -i, --interface    The interface to test internet connectivity with."
            echo "                     Default: Any interface"
            echo "  -u, --url          A URL or comma seperated list of URLs that should be accessible."
            echo "                     Default: https://connectivity-check.ubuntu.com"
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

if [ -z "$URL" ]; then
    URL="https://connectivity-check.ubuntu.com"
fi

test_interface "$INTERFACE" "$URL"
