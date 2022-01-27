#!/usr/bin/env python3
#
# fio - Run fio on supplied drive.
#
# Author: Newell Jensen <newell.jensen@canonical.com>
#         Lee Trager <lee.trager@canonical.com>
#
# Copyright (C) 2017-2020 Canonical
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
# name: fio
# title: Storage benchmark
# description: Run Fio benchmarking against selected storage devices.
# tags: storage
# script_type: testing
# hardware_type: storage
# parallel: instance
# results:
#  random_read:
#   title: Random read
#   description: Read speed when reading randomly from the disk.
#  random_read_iops:
#   title: Random read IOPS
#   description: IOPS when reading randomly from the disk.
#  sequential_read:
#   title: Sequential read
#   description: Read speed when reading sequentialy from the disk.
#  sequential_read_iops:
#   title: Sequential read IOPS
#   description: IOPS when reading sequentialy from the disk.
#  random_write:
#   title: Random write
#   description: Write speed when reading randomly from the disk.
#  random_write_iops:
#   title: Random write IOPS
#   description: IOPS when reading randomly from the disk.
#  sequential_write:
#   title: Sequential write
#   description: Write speed when reading sequentialy from the disk.
#  sequential_write_iops:
#   title: Sequential write IOPS
#   description: IOPS when reading sequentialy from the disk.
# parameters:
#  storage:
#    type: storage
#    argument_format: '{path}'
# packages: {apt: fio}
# destructive: true
# --- End MAAS 1.0 script metadata ---


import argparse
from copy import deepcopy
import json
import os
import re
from subprocess import CalledProcessError, check_output
import sys

import yaml

# When given --output-format=normal,json fio > 3 outputs both normal
# and json format. Older versions just output the normal format.
CMD = [
    "sudo",
    "-n",
    "fio",
    "--randrepeat=1",
    "--ioengine=libaio",
    "--direct=1",
    "--gtod_reduce=1",
    "--name=fio_test",
    "--iodepth=64",
    "--size=4G",
    "--output-format=normal,json",
]


REGEX = re.compile(
    r"""
    (
        # fio-3+ outputs both formats, this regex pulls out the JSON.
        (?P<pre_output>[^\{]*)(?P<json>^{.*^}$\n)(?P<post_output>.*)
    ) | (
        # fio < 3 will only output the normal output. Search for the
        # values we need.
        (
            ^\s+(read\s*:|write:).*
            bw=(?P<bw>.+)(?P<bw_unit>[KMG]B/s),.*iops=(?P<iops>\d+)
        )
    )
""",
    re.MULTILINE | re.DOTALL | re.VERBOSE,
)


def get_blocksize(blockdevice):
    """Return the block size of the block device."""
    blockname = os.path.basename(blockdevice)
    with open("/sys/block/%s/queue/physical_block_size" % blockname) as f:
        return int(f.read())


def run_cmd(readwrite, result_break=True):
    """Execute `CMD` and return output or exit if error."""
    cmd = deepcopy(CMD)
    cmd.append("--readwrite=%s" % readwrite)
    print("Running command: %s\n" % " ".join(cmd))
    try:
        stdout = check_output(cmd)
    except CalledProcessError as e:
        sys.stderr.write("fio failed to run!\n")
        sys.stdout.write(e.stdout.decode())
        if e.stderr is not None:
            sys.stderr.write(e.stderr.decode())
        sys.exit(e.returncode)

    stdout = stdout.decode()
    match = REGEX.search(stdout)
    if match is not None:
        regex_results = match.groupdict()
    else:
        regex_results = {}
    if regex_results["json"] is not None:
        # fio >= 3 - Only print the output, parse the JSON.
        full_output = ""
        for output in ["pre_output", "post_output"]:
            if regex_results[output] is not None:
                full_output += regex_results[output].strip()
        print(full_output)
        fio_dict = json.loads(regex_results["json"])["jobs"][0][
            "read" if "read" in readwrite else "write"
        ]
        results = {"bw": int(fio_dict["bw"]), "iops": int(fio_dict["iops"])}
    else:
        # fio < 3 - Print the output, the regex should of found the results.
        print(stdout)
        bw = regex_results.get("bw")
        if bw is not None:
            # JSON output in fio >= 3 always returns bw in KB/s. Normalize here
            # so units are always the same.
            multiplier = {"KB/s": 1, "MB/s": 1000, "GB/s": 1000 * 1000}
            bw = int(float(bw) * multiplier[regex_results["bw_unit"]])
        iops = regex_results.get("iops")
        if iops is not None:
            iops = int(iops)
        results = {"bw": bw, "iops": iops}
    if result_break:
        print("\n%s\n" % str("-" * 80))
    return results


def run_fio(blockdevice):
    """Execute fio tests for supplied storage device.

    Performs random and sequential read and write tests.
    """
    CMD.append("--filename=%s" % blockdevice)
    CMD.append("--bs=%s" % get_blocksize(blockdevice))
    random_read = run_cmd("randread")
    sequential_read = run_cmd("read")
    random_write = run_cmd("randwrite")
    sequential_write = run_cmd("write", False)

    # Write out YAML file if RESULT_PATH is set.
    result_path = os.environ.get("RESULT_PATH")
    if result_path is not None:
        results = {
            "results": {
                "random_read": "%s KB/s" % random_read["bw"],
                "random_read_iops": random_read["iops"],
                "sequential_read": "%s KB/s" % sequential_read["bw"],
                "sequential_read_iops": sequential_read["iops"],
                "random_write": "%s KB/s" % random_write["bw"],
                "random_write_iops": random_write["iops"],
                "sequential_write": "%s KB/s" % sequential_write["bw"],
                "sequential_write_iops": sequential_write["iops"],
            }
        }
        with open(result_path, "w") as results_file:
            yaml.safe_dump(results, results_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fio Hardware Testing.")
    parser.add_argument(
        "blockdevice", help="The blockdevice you want to test. e.g. /dev/sda"
    )
    args = parser.parse_args()
    sys.exit(run_fio(args.blockdevice))
