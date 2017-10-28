#!/usr/bin/env python3
#
# fio - Run fio on supplied drive.
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
#  storage: {type: storage}
# packages: {apt: fio}
# destructive: true
# --- End MAAS 1.0 script metadata ---


import argparse
from copy import deepcopy
import os
import re
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)
import sys

import yaml


CMD = [
    'sudo', '-n', 'fio', '--randrepeat=1', '--ioengine=libaio',
    '--direct=1', '--gtod_reduce=1', '--name=fio_test', '--bs=4k',
    '--iodepth=64', '--size=4G'
]

REGEX = b"bw=([0-9\.]+[a-zA-Z]+/s),\siops=([0-9]+)"


def run_cmd(cmd):
    """Execute `cmd` and return output or exit if error."""
    proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
    # Currently, we are piping stderr to STDOUT.
    stdout, _ = proc.communicate()

    # Print stdout to the console.
    if stdout is not None:
        print('Running command: %s\n' % ' '.join(cmd))
        print(stdout.decode())
        print('-' * 80)
    if proc.returncode == 0:
        return stdout, proc.returncode
    sys.exit(proc.returncode)


def run_fio_test(readwrite, result_path):
    """Run fio for the given type of test specified by `cmd`."""
    cmd = deepcopy(CMD)
    cmd.append('--readwrite=%s' % readwrite)
    stdout, returncode = run_cmd(cmd)
    if result_path is not None:
        # Parse the results for the desired information and
        # then wrtie this to the results file.
        match = re.search(REGEX, stdout)
        if match is None:
            print("Warning: results could not be found.")
        return match


def run_fio(storage):
    """Execute fio tests for supplied storage device.

    Performs random and sequential read and write tests.
    """
    result_path = os.environ.get("RESULT_PATH")
    CMD.append('--filename=%s' % storage)
    random_read_match = run_fio_test("randread", result_path)
    sequential_read_match = run_fio_test("read", result_path)
    random_write_match = run_fio_test("randwrite", result_path)
    sequential_write_match = run_fio_test("write", result_path)

    # Write out YAML file if RESULT_PATH is set.
    # The status is hardcoded at the moment because there isn't a
    # degraded state yet for fio.  This most likely will change in
    # the future when there is an agreed upon crtteria for fio to
    # mark a storage device in the degraded state based on one of
    # its tests.
    if all(var is not None for var in [
            result_path, random_read_match, sequential_read_match,
            random_write_match, sequential_write_match]):
        results = {
            'status': "passed",
            'results': {
                'random_read': random_read_match.group(1).decode(),
                'random_read_iops': random_read_match.group(2).decode(),
                'sequential_read': sequential_read_match.group(1).decode(),
                'sequential_read_iops': (
                    sequential_read_match.group(2).decode()),
                'random_write': random_write_match.group(1).decode(),
                'random_write_iops': random_write_match.group(2).decode(),
                'sequential_write': sequential_write_match.group(1).decode(),
                'sequential_write_iops': (
                    sequential_write_match.group(2).decode()),
            }
        }
        with open(result_path, 'w') as results_file:
            yaml.safe_dump(results, results_file)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Fio Hardware Testing.')
    parser.add_argument(
        '--storage', dest='storage',
        help='path to storage device you want to test. e.g. /dev/sda')
    args = parser.parse_args()
    sys.exit(run_fio(args.storage))
