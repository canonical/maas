#!/usr/bin/env python3
#
# smartctl - Run smartctl on all drives in parellel
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
from subprocess import (
    CalledProcessError,
    check_call,
    check_output,
    DEVNULL,
    PIPE,
    Popen,
    STDOUT,
    TimeoutExpired,
)
import sys
from threading import Thread
from time import sleep

# We're just reading the SMART data or asking the drive to run a self test.
# If this takes more then a minute there is something wrong the with drive.
TIMEOUT = 60


class RunSmartCtl(Thread):

    def __init__(self, smartctl_args, test=None):
        super().__init__(name=smartctl_args[0])
        self.smartctl_args = smartctl_args
        self.test = test
        self.running_test_failed = False
        self.output = b''
        self.timedout = False

    def _run_smartctl_selftest(self):
        try:
            # Start testing.
            check_call(
                ['sudo', 'smartctl', '-s', 'on', '-t', self.test] +
                self.smartctl_args, timeout=TIMEOUT, stdout=DEVNULL,
                stderr=DEVNULL)
        except (TimeoutExpired, CalledProcessError):
            self.running_test_failed = True
        else:
            # Wait for testing to complete.
            status_regex = re.compile(
                'Self-test execution status:\s+\(\s*(?P<status>\d+)\s*\)')
            while True:
                try:
                    stdout = check_output(
                        ['sudo', 'smartctl', '-c'] + self.smartctl_args,
                        timeout=TIMEOUT)
                except (TimeoutExpired, CalledProcessError):
                    self.running_test_failed = True
                    break
                else:
                    m = status_regex.search(stdout.decode('utf-8'))
                    if m is not None and int(m.group('status')) == 0:
                        break
                    else:
                        sleep(1)

    def run(self):
        if self.test is not None:
            self._run_smartctl_selftest()

        # Run smartctl and capture its output. Once all threads have completed
        # we'll output the results serially so output is properly grouped.
        with Popen(
                ['sudo', 'smartctl', '--xall'] + self.smartctl_args,
                stdout=PIPE, stderr=STDOUT) as proc:
            try:
                self.output, _ = proc.communicate(timeout=TIMEOUT)
            except TimeoutExpired:
                proc.kill()
                self.timedout = True
            self.returncode = proc.returncode

    @property
    def was_successful(self):
        # smartctl returns 0 when there are no errors. It returns 4 if a SMART
        # or ATA command to the disk failed. This is surprisingly common so
        # ignore it.
        return self.returncode in {0, 4}


def list_supported_drives():
    """Ask smartctl to give us a list of drives which have SMART data.

    :return: A list of drives that have SMART data.
    """
    # Gather a list of connected ISCSI drives. ISCSI has SMART data but we
    # only want to scan local disks during testing.
    try:
        output = check_output(
            ['sudo', 'iscsiadm', '-m', 'session', '-P', '3'], timeout=TIMEOUT,
            stderr=DEVNULL)
    except (TimeoutExpired, CalledProcessError):
        # If this command failed ISCSI is most likely not running/installed.
        # Ignore the error and move on, worst case scenario we run smartctl
        # on ISCSI drives.
        iscsi_drives = []
    else:
        iscsi_drives = re.findall(
            'Attached scsi disk (?P<disk>\w+)', output.decode('utf-8'))

    drives = []
    smart_support_regex = re.compile('SMART support is:\s+Available')
    output = check_output(['sudo', 'smartctl', '--scan-open'], timeout=TIMEOUT)
    for line in output.decode('utf-8').splitlines():
        try:
            # Each line contains the drive and the device type along with any
            # options needed to run smartctl against the drive.
            drive_with_device_type = line.split('#')[0].split()
        except IndexError:
            continue
        drive = drive_with_device_type[0]
        if drive != '' and drive.split('/')[-1] not in iscsi_drives:
            # Check that SMART is actually supported on the drive.
            with Popen(['sudo', 'smartctl', '-i'] + drive_with_device_type,
                       stdout=PIPE, stderr=DEVNULL) as proc:
                try:
                    output, _ = proc.communicate(timeout=TIMEOUT)
                except TimeoutExpired:
                    sys.stderr.write(
                        "Unable to determine if %s supports SMART" % drive)
                else:
                    m = smart_support_regex.search(output.decode('utf-8'))
                    if m is not None:
                        drives.append(drive_with_device_type)
    return drives


def run_smartctl(test=None):
    """Run smartctl against all drives on the system with SMART data.

    Runs smartctl against all drives on the system each in their own thread.
    Once SMART data has been read from all drives output the result and if
    smartctl timedout or detected an error.

    :return: The number of drives which SMART indicates are failing.
    """
    threads = []
    for smartctl_args in list_supported_drives():
        thread = RunSmartCtl(smartctl_args, test)
        thread.start()
        threads.append(thread)

    smartctl_failures = 0
    for thread in threads:
        thread.join()
        drive = thread.smartctl_args[0]
        dashes = '-' * int((80.0 - (2 + len(drive))) / 2)
        print('%s %s %s' % (dashes, drive, dashes))
        print()

        if thread.running_test_failed:
            smartctl_failures += 1
            print('Failed to start and wait for smartctl self-test %s', test)
            print()
        if thread.timedout:
            smartctl_failures += 1
            print(
                'Running `smartctl --xall %s` timed out!' %
                ' '.join(thread.drive_with_device_type))
            print()
        elif not thread.was_successful:
            # smartctl returns 0 when there are no errors. It returns 4 if
            # a SMART or ATA command to the disk failed. This is surprisingly
            # common so ignore it.
            smartctl_failures += 1
            print(
                'Error, `smartctl --xall %s` returned %d!' % (
                    ' '.join(thread.drive_with_device_type),
                    thread.returncode))
            print('See the smartctl man page for return code meaning')
            print()
        print(thread.output.decode('utf-8'))

    return smartctl_failures


if __name__ == '__main__':
    # The MAAS ephemeral environment runs apt-get update for us.
    # Don't use timeout here incase the mirror is running really slow.
    check_call(['sudo', 'apt-get', '-y', 'install', 'smartmontools'])

    # Determine which test should be run based from the first argument or
    # script name.
    if len(sys.argv) > 1:
        test = sys.argv[1]
    else:
        test = None
        for test_name in {'short', 'long', 'conveyance'}:
            if test_name in sys.argv[0]:
                test = test_name
                break
    sys.exit(run_smartctl(test))
