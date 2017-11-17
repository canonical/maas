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
# title: {{title}}
# description: {{description}}
# tags: {{if 'validate' in name}}commissioning{{endif}}
# script_type: test
# hardware_type: storage
# parallel: instance
# parameters:
#   storage: {type: storage}
# packages: {apt: smartmontools}
# timeout: {{timeout}}
# --- End MAAS 1.0 script metadata ---

import argparse
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
from time import sleep

# We're just reading the SMART data or asking the drive to run a self test.
# If this takes more then a minute there is something wrong the with drive.
TIMEOUT = 60


def check_SMART_support(storage):
    """Check if SMART support is available for storage device.

    If SMART support is not available, exit the script.
    """
    smart_support_regex = re.compile('SMART support is:\s+Available')
    print(
        'INFO: Veriying SMART support for the following drive: %s' % storage)
    try:
        cmd = ['sudo', '-n', 'smartctl', '--all', storage]
        print('INFO: Running command: %s\n' % ' '.join(cmd))
        output = check_output(cmd, timeout=TIMEOUT, stderr=STDOUT)
    except TimeoutExpired:
        print(
            "ERROR: Unable to determine if the drive supports SMART. "
            "Command timed out after %s seconds." % (storage, TIMEOUT))
        sys.exit(1)
    except CalledProcessError as e:
        output = e.output
        if output is None:
            print(
                "INFO: Unable to determine if the drive supports SMART. "
                "Command failed to run and did not return any output. ")
            sys.exit(1)

    match = smart_support_regex.search(output.decode('utf-8'))
    if match is None:
        print(
            'INFO: Unable to run test. The following drive '
            'does not support SMART: %s\n' % storage)
        sys.exit()
    print('INFO: SMART support is available; continuing...')


def run_smartctl_selftest(storage, test):
    """Run smartctl self test."""
    try:
        # Start testing.
        cmd = ['sudo', '-n', 'smartctl', '-s', 'on', '-t', test, storage]
        print('INFO: Running command: %s\n' % ' '.join(cmd))
        check_call(cmd, timeout=TIMEOUT, stdout=DEVNULL, stderr=DEVNULL)
    except (TimeoutExpired, CalledProcessError):
        print(
            'ERROR: Failed to start and wait for smartctl '
            'self-test: %s' % test)
        return False
    else:
        # Wait for testing to complete.
        status_regex = re.compile(
            'Self-test execution status:\s+\(\s*(?P<status>\d+)\s*\)'
            '\s+Self-test routine in progress')
        while True:
            try:
                stdout = check_output(
                    ['sudo', '-n', 'smartctl', '-c', storage],
                    timeout=TIMEOUT)
            except (TimeoutExpired, CalledProcessError):
                print('ERROR: Failed to start and wait for smartctl self-test:'
                      ' %s' % test)
                return False
            else:
                m = status_regex.search(stdout.decode('utf-8'))
                if m is None:
                    # The test has finished running because we cannot find
                    # regex match saying that's in-progress.
                    break
                else:
                    # This is the time the test waits before checking for
                    # completion. It needs not be too short otherwise it
                    # can cause tests to get stuck
                    sleep(30)

    return True


def run_smartctl(storage, test=None):
    """Run smartctl against storage drive on the system with SMART data."""
    # Check to see if SMART is supported before trying to run tests.
    smartctl_passed = True
    check_SMART_support(storage)
    if test not in ('validate', None):
        smartctl_passed = run_smartctl_selftest(storage, test)

    print('INFO: Verifying and/or validating SMART tests...')
    cmd = ['sudo', '-n', 'smartctl', '--xall', storage]
    print('INFO: Running command: %s\n' % ' '.join(cmd))
    # Run smartctl and capture its output.
    with Popen(cmd, stdout=PIPE, stderr=STDOUT) as proc:
        try:
            output, _ = proc.communicate(timeout=TIMEOUT)
        except TimeoutExpired:
            proc.kill()
            print('INFO: Running `smartctl --xall %s` timed out!' % storage)
            smartctl_passed = False
        else:
            if proc.returncode != 0 and proc.returncode != 4:
                print('FAILURE: SMART tests have FAILED for: %s' % storage)
                print('The test exited with return code %s! See the smarctl '
                      'manpage for information on the return code meaning. '
                      'For more information on the test failures, review the '
                      'test output provided below.' % proc.returncode)
                smartctl_passed = False
            else:
                print('SUCCESS: SMART tests have PASSED for: %s\n' % storage)

            if output is not None:
                print('---------------------------------------------------\n')
                print(output.decode('utf-8'))
            return 0 if proc.returncode == 4 else proc.returncode

    return 0 if smartctl_passed else 1

if __name__ == '__main__':
    # Determine which test should be run based from the script name.
    test = None
    for test_name in {'short', 'long', 'conveyance'}:
        if test_name in sys.argv[0]:
            test = test_name
            break

    parser = argparse.ArgumentParser(description='SMARTCTL Hardware Testing.')
    parser.add_argument(
        '--storage', dest='storage',
        help='path to storage device you want to test. e.g. /dev/sda')
    args = parser.parse_args()
    sys.exit(run_smartctl(args.storage, test))
