#!/usr/bin/env python3
#
# 7zip - Run 7zip benchmarking on CPU(s).
#
# Author: Newell Jensen <newell.jensen@canonical.com>
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
# name: 7z
# title: CPU benchmark
# description: Run 7zip CPU benchmarking.
# tags: cpu
# script_type: testing
# hardware_type: cpu
# timeout: 300
# results:
#  compression_ru_mips:
#   title: Compression RU MIPS
#   description: >
#    Compression rating normalized for 100% of CPU usage.
#    This shows the performance of one average CPU thread.
#  compression_rating_mips:
#   title: Compression Rating MIPS
#   description: >
#    Compression rating for CPU usage.
#    This shows the performance of all CPU threads combined.
#  decompression_ru_mips:
#   title: Decompression RU MIPS
#   description: >
#    Decompression rating normalized for 100% of CPU usage.
#    This shows the performance of one average CPU thread.
#  decompression_rating_mips:
#   title: Decompression Rating MIPS
#   description: >
#    Decompression rating for CPU usage.
#    This shows the performance of all CPU threads combined.
# packages: {apt: p7zip-full}
# --- End MAAS 1.0 script metadata ---

import argparse
import os
import re
from subprocess import PIPE, Popen
import sys

import yaml

REGEX = b"Avr:(.*)"


def run_7z():
    result_path = os.environ.get("RESULT_PATH")
    cmd = ["7z", "b"]
    proc = Popen(cmd, stdout=PIPE, stderr=PIPE)
    stdout, stderr = proc.communicate()

    # Print stdout to the console.
    if stdout is not None:
        print("Running command: %s\n" % " ".join(cmd))
        print(stdout.decode())

    if proc.returncode != 0:
        if stderr is not None:
            sys.stderr.write(stderr.decode())
        sys.exit(proc.returncode)

    if result_path is not None:
        # Parse the results for the desired information and
        # then wrtie this to the results file.
        match = re.search(REGEX, stdout)
        if match is None:
            # Write to stderr here, as stdout is already wrtitten
            # to by the print funciton in run_cmd.
            if stderr is not None:
                sys.stderr.write(stderr.decode())
            sys.exit(proc.returncode)

        # Write out YAML file if RESULT_PATH is set.
        # The result is hardcoded at the moment because there isn't a
        # degraded state yet for 7z.  This most likely will change in
        # the future when there is an agreed upon crtteria for 7z to
        # mark a machine in the degraded state based on one of its tests.
        averages = match.group(1).split()
        results = {
            "status": "passed",
            "results": {
                "compression_ru_mips": averages[1].decode(),
                "compression_rating_mips": averages[2].decode(),
                "decompression_ru_mips": averages[4].decode(),
                "decompression_rating_mips": averages[5].decode(),
            },
        }
        with open(result_path, "w") as results_file:
            yaml.safe_dump(results, results_file)

    return proc.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="7z Hardware Benchmark Testing."
    )
    args = parser.parse_args()
    sys.exit(run_7z())
