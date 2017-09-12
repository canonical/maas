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
# parameters:
#   storage: {type: storage}
# destructive: {{if 'destructive' in name}}True{{else}}False{{endif}}
# --- End MAAS 1.0 script metadata ---

import argparse
import os
import re
from subprocess import (
    check_output,
    DEVNULL,
    PIPE,
    Popen,
    STDOUT,
)
import sys

import yaml


REGEX = b", ([0-9]+) bad blocks found"


def run_badblocks(storage, destructive=False):
    """Run badblocks against storage drive."""
    result_path = os.environ.get("RESULT_PATH")
    blocksize = check_output(
        ['sudo', '-n', 'blockdev', '--getbsz', storage],
        stderr=DEVNULL).strip().decode()
    if destructive:
        cmd = [
            'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-w',
            storage]
    else:
        cmd = [
            'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-n',
            storage]

    print('Running command: %s\n' % ' '.join(cmd))
    proc = Popen(cmd, stdout=PIPE, stderr=STDOUT)
    stdout, _ = proc.communicate()

    # Print stdout to the console.
    if stdout is not None:
        print(stdout.decode())

    if result_path is not None:
        # Parse the results for the desired information and
        # then wrtie this to the results file.
        match = re.search(REGEX, stdout)
        if match is not None:
            results = {
                'results': {
                    'badblocks': int(match.group(1).decode()),
                }
            }
            with open(result_path, 'w') as results_file:
                yaml.safe_dump(results, results_file)

    return proc.returncode


if __name__ == '__main__':
    # Determine if badblocks should run destructively from the script name.
    if 'destructive' in sys.argv[0]:
        destructive = True
    else:
        destructive = False

    parser = argparse.ArgumentParser(description='Badblocks Hardware Testing.')
    parser.add_argument(
        '--storage', dest='storage',
        help='path to storage device you want to test. e.g. /dev/sda')
    args = parser.parse_args()
    sys.exit(run_badblocks(args.storage, destructive))
