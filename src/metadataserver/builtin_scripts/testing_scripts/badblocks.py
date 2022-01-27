#!/usr/bin/env python3
#
# {{name}} - {{description}}
#
# Author: Lee Trager <lee.trager@canonical.com>
#         Newell Jensen <newell.jensen@canonical.com>
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
#
# --- Start MAAS 1.0 script metadata ---
# name: {{name}}
# title: Storage integrity
# description: {{description}}
# script_type: test
# hardware_type: storage
# parallel: instance
# results:
#   badblocks:
#     title: Bad blocks
#     description: The number of bad blocks found on the storage device.
#   read_errors:
#     title: Bad blocks read errors
#     description: >
#       The number of bad blocks read errors found on the storage device.
#   write_errors:
#     title: Bad blocks write errors
#     description: >
#       The number of bad blocks write errors found on the storage device.
#   comparison_errors:
#     title: Bad blocks comparison errors
#     description: >
#       The number of bad blocks comparison errors found on the storage device.
# parameters:
#   storage: {type: storage}
# destructive: {{if 'destructive' in name}}True{{else}}False{{endif}}
# --- End MAAS 1.0 script metadata ---

import argparse
import os
import re
from subprocess import check_output, PIPE, Popen, STDOUT
import sys

import yaml

# Give commands querying the system for info before running the test a
# short time out. These commands should finish nearly instantly, if they
# don't something is very wrong with the system.
TIMEOUT = 60


def get_block_size(storage):
    """Return the block size for the storage device."""
    cmd = ["sudo", "-n", "blockdev", "--getbsz", storage]
    print(
        "INFO: Determining %s block size by running `%s`"
        % (storage, " ".join(cmd))
    )
    return int(check_output(cmd, timeout=TIMEOUT))


def get_meminfo_key(meminfo, key):
    """Get key values from /proc/meminfo."""
    m = re.search(fr"{key}:\s+(?P<{key}>\d+)\s+kB", meminfo)
    if m is None or key not in m.groupdict():
        print("ERROR: Unable to find %s in /proc/meminfo" % key)
        sys.exit(1)
    try:
        return int(m.group(key))
    except Exception:
        print("ERROR: Unable to convert %s into an int" % key)
        sys.exit(1)


def get_parallel_blocks(block_size):
    """Return the number of blocks to be tested in parallel."""
    print("INFO: Determining the amount of blocks to be tested in parallel")
    with open("/proc/sys/vm/min_free_kbytes") as f:
        min_free_kbytes = int(f.read())
    with open("/proc/meminfo") as f:
        meminfo = f.read()
    memtotal = get_meminfo_key(meminfo, "MemTotal")
    memfree = get_meminfo_key(meminfo, "MemFree")
    # Make sure badblocks doesn't consume all memory. As a minimum reserve
    # the min_Free_kbytes or the value of 0.77% of memory to ensure not to
    # trigger the OOM killer.
    reserve = int(memtotal * 0.0077)
    if reserve < min_free_kbytes:
        reserve = min_free_kbytes + 10240
    # Get available memory in bytes
    memavailable = (memfree - reserve) * 1024
    # badblocks is launched in parallel by maas-run-remote-scripts so account
    # for other storage devices being tested in parallel
    output = check_output(
        ["lsblk", "--exclude", "1,2,7", "-d", "-P", "-o", "NAME,MODEL,SERIAL"]
    )
    output = output.decode("utf-8")
    storage_devices = len(output.splitlines())
    parallel_blocks = int(memavailable / block_size / storage_devices)
    # Most systems will be able to test hundreds of thousands of blocks at once
    # using the algorithm above. Don't get too carried away, limit to 50000.
    return min(parallel_blocks, 50000)


def run_badblocks(storage, destructive=False):
    """Run badblocks against storage drive."""
    blocksize = get_block_size(storage)
    parallel_blocks = get_parallel_blocks(blocksize)
    if destructive:
        cmd = [
            "sudo",
            "-n",
            "badblocks",
            "-b",
            str(blocksize),
            "-c",
            str(parallel_blocks),
            "-v",
            "-f",
            "-s",
            "-w",
            storage,
        ]
    else:
        cmd = [
            "sudo",
            "-n",
            "badblocks",
            "-b",
            str(blocksize),
            "-c",
            str(parallel_blocks),
            "-v",
            "-f",
            "-s",
            "-n",
            storage,
        ]

    print("INFO: Running command: %s\n" % " ".join(cmd))
    proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
    stdout, _ = proc.communicate()
    stdout = stdout.decode()

    # Print stdout to the console.
    print(stdout)

    m = re.search(
        r"^Pass completed, (?P<badblocks>\d+) bad blocks found. "
        r"\((?P<read>\d+)\/(?P<write>\d+)\/(?P<comparison>\d+) errors\)$",
        stdout,
        re.M,
    )
    badblocks = int(m.group("badblocks"))
    read_errors = int(m.group("read"))
    write_errors = int(m.group("write"))
    comparison_errors = int(m.group("comparison"))
    result_path = os.environ.get("RESULT_PATH")
    if result_path is not None:
        results = {
            "results": {
                "badblocks": badblocks,
                "read_errors": read_errors,
                "write_errors": write_errors,
                "comparison_errors": comparison_errors,
            }
        }
        with open(result_path, "w") as results_file:
            yaml.safe_dump(results, results_file)

    # LP: #1733923 - Badblocks normally returns 0 no matter the result. If any
    # errors are found fail the test.
    if (
        proc.returncode
        + badblocks
        + read_errors
        + write_errors
        + comparison_errors
    ) != 0:
        print("FAILURE: Test FAILED!")
        print("INFO: %s badblocks found" % badblocks)
        print("INFO: %s read errors found" % read_errors)
        print("INFO: %s write errors found" % write_errors)
        print("INFO: %s comparison errors found" % comparison_errors)
        return 1
    else:
        print("SUCCESS: Test PASSED!")
        return 0


if __name__ == "__main__":
    # Determine if badblocks should run destructively from the script name.
    if "destructive" in sys.argv[0]:
        destructive = True
    else:
        destructive = False

    parser = argparse.ArgumentParser(description="Badblocks Hardware Testing.")
    parser.add_argument(
        "--storage",
        dest="storage",
        help="path to storage device you want to test. e.g. /dev/sda",
    )
    args = parser.parse_args()
    sys.exit(run_badblocks(args.storage, destructive))
