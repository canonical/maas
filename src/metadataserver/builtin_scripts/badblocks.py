#!/usr/bin/env python3
#
# badblocks - Run badblocks on all drives in parallel
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

import re
import shlex
from subprocess import (
    CalledProcessError,
    check_output,
    DEVNULL,
    PIPE,
    Popen,
    STDOUT,
    TimeoutExpired,
)
import sys
from threading import Thread

# Short running commands which are used to query info about the drive should
# work in under a minute otherwise assume a failure.
TIMEOUT = 60


class RunBadBlocks(Thread):

    def __init__(self, drive, destructive=False):
        super().__init__(name=drive['PATH'])
        self.drive = drive
        self.destructive = destructive
        self.output = b''
        self.returncode = None

    def run(self):
        blocksize = check_output(
            ['sudo', '-n', 'blockdev', '--getbsz', self.drive['PATH']],
            timeout=TIMEOUT, stderr=DEVNULL).strip()
        if self.destructive:
            cmd = [
                'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-w',
                self.drive['PATH']]
        else:
            cmd = [
                'sudo', '-n', 'badblocks', '-b', blocksize, '-v', '-n',
                self.drive['PATH']]
        # Run badblocks and capture its output. Once all threads have completed
        # output the results serially so output is proerly grouped.
        with Popen(cmd, stdout=PIPE, stderr=STDOUT) as proc:
            self.output, _ = proc.communicate()
            self.returncode = proc.returncode


def list_drives():
    """List all drives available to test

    :return: A list of drives that have SMART data.
    """
    # Gather a list of connected ISCSI drives to ignore.
    try:
        output = check_output(
            ['sudo', '-n', 'iscsiadm', '-m', 'session', '-P', '3'],
            timeout=TIMEOUT, stderr=DEVNULL)
    except (TimeoutExpired, CalledProcessError):
        # If this command failed ISCSI is most likely not running/installed.
        # Ignore the error and move on.
        iscsi_drives = []
    else:
        iscsi_drives = re.findall(
            'Attached scsi disk (?P<disk>\w+)', output.decode('utf-8'))

    try:
        lsblk_output = check_output(
            [
                'lsblk', '--exclude', '1,2,7', '-d', '-P', '-o',
                'NAME,RO,MODEL,SERIAL',
            ], timeout=TIMEOUT).decode('utf-8')
    except CalledProcessError:
        # The SERIAL column is unsupported in the Trusty version of lsblk. Try
        # again without it.
        lsblk_output = check_output(
            [
                'lsblk', '--exclude', '1,2,7', '-d', '-P', '-o',
                'NAME,RO,MODEL',
            ], timeout=TIMEOUT).decode('utf-8')
    drives = []
    for line in lsblk_output.splitlines():
        drive = {}
        for part in shlex.split(line):
            key, value = part.split('=')
            drive[key.strip()] = value.strip()
        if drive['NAME'] not in iscsi_drives and drive['RO'] == '0':
            drive['PATH'] = '/dev/%s' % drive['NAME']
            drives.append(drive)

    return drives


def run_badblocks(destructive=False):
    """Run badblocks against all drives on the system.

    Runs badblocks against all drives on the system each in their own thread.
    Once badblocks has finished output the result.

    :return: The number of drives which badblocks detected as failures.
    """
    threads = []
    for drive in list_drives():
        thread = RunBadBlocks(drive, destructive)
        thread.start()
        threads.append(thread)

    badblock_failures = 0
    for thread in threads:
        thread.join()
        dashes = '-' * int((80.0 - (2 + len(thread.drive['PATH']))) / 2)
        print('%s %s %s' % (dashes, thread.drive['PATH'], dashes))
        print('Model:  %s' % thread.drive['MODEL'])
        # The SERIAL column is only available in newer versions of lsblk. This
        # can be removed with Trusty support.
        if 'SERIAL' in thread.drive:
            print('Serial: %s' % thread.drive['SERIAL'])
        print()

        if thread.returncode != 0:
            badblock_failures += 1
            print('Badblocks exited with %d!' % thread.returncode)
            print()
        print(thread.output.decode('utf-8'))

    return badblock_failures


if __name__ == '__main__':
    # Determine if badblocks should run destructively from the first argument
    # or script name.
    if len(sys.argv) > 1 and sys.argv[1] == 'destructive':
        destructive = True
    elif 'destructive' in sys.argv[0]:
        destructive = True
    else:
        destructive = False

    sys.exit(run_badblocks(destructive))
