#!/usr/bin/env python3
#
# {{name}} - {{description}}
#
# Author: Lee Trager <lee.trager@canonical.com>
#         Newell Jensen <newell.jensen@canonical.com>
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
# name: {{name}}
# title: {{title}}
# description: {{description}}
# tags: {{if 'validate' in name}}commissioning{{endif}}
# script_type: test
# hardware_type: storage
# parallel: instance
# parameters:
#   storage:
#     type: storage
#     argument_format: '{path}'
# packages: {apt: smartmontools}
# timeout: {{timeout}}
# --- End MAAS 1.0 script metadata ---

import argparse
import glob
import os
import re
from subprocess import (
    CalledProcessError,
    check_output,
    DEVNULL,
    STDOUT,
    TimeoutExpired,
)
import sys
from time import sleep

import yaml

# We're just reading the SMART data or asking the drive to run a self test.
# If this takes more then a minute there is something wrong the with drive.
TIMEOUT = 60


def run_smartctl(blockdevice, args, device=None, output=False, **kwargs):
    """Construct and run a smartctl command."""
    cmd = ["sudo", "-n", "smartctl"]
    if device:
        cmd += ["-d", device]
    cmd += args
    cmd += [blockdevice]
    if output:
        print("INFO: Running command: %s" % " ".join(cmd))
    return check_output(cmd, timeout=TIMEOUT, **kwargs).decode(
        errors="replace"
    )


def run_storcli(args, output=False, **kwargs):
    """Construct and run a storcli command."""
    if os.path.exists("/opt/MegaRAID/storcli/storcli64"):
        storcli = "/opt/MegaRAID/storcli/storcli64"
    else:
        storcli = "storcli64"
    cmd = ["sudo", "-n", storcli] + args
    if output:
        print("INFO: Running command: %s" % " ".join(cmd))
    return check_output(cmd, timeout=TIMEOUT, **kwargs).decode(
        errors="replace"
    )


def make_device_name(blockdevice, device=None):
    """Create a device name string for output."""
    if device:
        return "%s %s" % (blockdevice, device)
    else:
        return blockdevice


def exit_skipped():
    """Write a result YAML indicating the test has been skipped."""
    result_path = os.environ.get("RESULT_PATH")
    if result_path is not None:
        with open(result_path, "w") as results_file:
            yaml.safe_dump({"status": "skipped"}, results_file)
    sys.exit()


def find_matching_megaraid_controller(blockdevice):
    """Return the MegaRAID controller number matching the blockdevice."""
    output = run_storcli(["show"], output=True)
    m = re.search(
        r"^Number of Controllers = (?P<controllers>\d+)$", output, re.MULTILINE
    )
    if not m:
        print("ERROR: Unable to determine the amount of MegaRAID controllers!")
        return exit_skipped()

    controllers = int(m["controllers"])
    vds_regex = re.compile(r"^Virtual Drives = (?P<vds>\d+)$", re.MULTILINE)
    scsi_id_regex = re.compile(
        r"^SCSI NAA Id = (?P<scsi_id>\w+)$", re.MULTILINE
    )
    for controller in range(0, controllers):
        output = run_storcli(["/c%d" % controller, "show"])
        m = vds_regex.search(output)
        if m is None:
            continue
        vds = int(m["vds"])
        for vd in range(0, vds):
            output = run_storcli(
                ["/c%d/v%d" % (controller, vd), "show", "all"]
            )
            m = scsi_id_regex.search(output)
            if m is None:
                continue
            scsi_id = m["scsi_id"]
            for drive in glob.glob("/dev/disk/by-id/*%s*" % scsi_id):
                if os.path.realpath(drive) == os.path.realpath(blockdevice):
                    return controller

    print(
        "ERROR: Unable to find a MegaRAID controller assoicated with %s"
        % blockdevice
    )
    return exit_skipped()


def detect_megaraid_config(blockdevice):
    """If MEGARAID tools available use them to discover all disks in RAID."""
    print("INFO: MegaRAID device detected!")
    print("INFO: Checking if storcli is available...")
    # The storcli Debian package installs storcli64 outside of the standard
    # PATH. Check for it there, then fallback to checking stand PATH.
    if not os.path.exists("/opt/MegaRAID/storcli/storcli64"):
        try:
            check_output(["which", "storcli64"], timeout=TIMEOUT)
        except (TimeoutExpired, CalledProcessError):
            print(
                "ERROR: storcli64 not found! Download and install storcli "
                "from Broadcom before running."
            )
            return exit_skipped()

    controller = find_matching_megaraid_controller(blockdevice)
    output = run_storcli(["/c%d" % controller, "/eall", "/sall", "show"])
    return [
        int(i)
        for i in re.findall(r"^\d+:\d+\s+(?P<DID>\d+)", output, re.MULTILINE)
    ]


def check_SMART_support(blockdevice, device=None):
    """Check if SMART support is available for blockdevice device."""
    device_name = make_device_name(blockdevice, device)
    print(
        "INFO: Verifying SMART support for the following drive: %s"
        % device_name
    )
    try:
        output = run_smartctl(
            blockdevice, ["--all"], device, output=True, stderr=STDOUT
        )
    except TimeoutExpired:
        print(
            "ERROR: Unable to determine if %s supports SMART. "
            "Command timed out after %s seconds." % (device_name, TIMEOUT)
        )
        raise
    except CalledProcessError as e:
        if not e.output:
            print(
                "ERROR: Unable to determine if %s supports SMART. "
                "Command failed to run and did not return any output. "
                % device_name
            )
            raise
        else:
            output = e.output.decode(errors="replace")

    if (
        re.search(
            r"(SMART support is:\s+Available)|"
            r"(SMART overall-health self-assessment test result)",
            output,
        )
        is None
    ):
        if re.search(r"Product:\s+MegaRAID", output) is not None:
            return "megaraid", detect_megaraid_config(blockdevice)
        else:
            print(
                "INFO: Unable to run test. The following drive "
                "does not support SMART: %s" % device_name
            )
            return exit_skipped()

    print("INFO: SMART support is available; continuing...")
    return None, []


def run_smartctl_selftest(blockdevice, test, device=None):
    """Run smartctl self test."""
    try:
        # Start testing.
        run_smartctl(
            blockdevice, ["-t", test], device, output=True, stderr=DEVNULL
        )
    except (TimeoutExpired, CalledProcessError):
        print("ERROR: Failed to start smartctl self-test: %s" % test)
        raise


def wait_smartctl_selftest(blockdevice, test, device=None):
    """Wait for a smartctl selftest to complete."""
    print("INFO: Waiting for SMART selftest %s to complete..." % test)
    status_regex = re.compile(
        r"Self-test execution status:\s+\(\s*(?P<status>\d+)\s*\)"
        r"\s+Self-test routine in progress"
    )
    args = ["-c"]
    tried_alt = False
    while True:
        try:
            output = run_smartctl(blockdevice, args, device)
        except (TimeoutExpired, CalledProcessError):
            print("ERROR: Failed to start and wait for smartctl self-test")
            raise
        m = status_regex.search(output)
        if m is None and not tried_alt:
            # Some devices(MegaRAID) test progress with --all instead of -c
            args = ["--all"]
            status_regex = re.compile(
                r"Background %s\s+Self test in progress" % test
            )
            tried_alt = True
        elif m is None:
            # The test has finished running because we cannot find
            # a regex match saying that one is running.
            return
        else:
            # This is the time the test waits before checking for
            # completion. It needs not be too short otherwise it
            # can cause tests to get stuck
            sleep(30)


def check_smartctl(blockdevice, device=None):
    """Run smartctl against storage drive on the system with SMART data."""
    device_name = make_device_name(blockdevice, device)
    print("INFO: Verifying SMART data on %s" % device_name)
    try:
        output = run_smartctl(
            blockdevice, ["--xall"], device, output=True, stderr=STDOUT
        )
    except TimeoutExpired:
        print("ERROR: Validating %s timed out!" % device_name)
        raise
    except CalledProcessError as e:
        # A return code of 4 means a smartctl command failed or a checksum
        # error was discovered. This is surprisingly common so ignore it.
        if e.returncode != 4 or not e.output:
            print("FAILURE: SMART tests have FAILED for: %s" % device_name)
            print(
                "The test exited with return code %s! See the smarctl "
                "manpage for information on the return code meaning. "
                "For more information on the test failures, review the "
                "test output provided below." % e.returncode
            )
            raise
        else:
            output = e.output.decode(errors="replace")

    print("SUCCESS: SMART validation has PASSED for: %s" % device_name)
    if output is not None:
        print("-" * 80)
        print(output)


def execute_smartctl(blockdevice, test):
    """Execute smartctl."""
    try:
        device_type, bus_ids = check_SMART_support(blockdevice)
    except (TimeoutExpired, CalledProcessError):
        return False

    failure_detected = False
    if device_type:
        # Validate all drives in the RAID support SMART and start testing.
        for bus_id in bus_ids:
            device = "%s,%s" % (device_type, bus_id)
            try:
                check_SMART_support(blockdevice, device)
                if test != "validate":
                    run_smartctl_selftest(blockdevice, test, device)
            except (TimeoutExpired, CalledProcessError):
                failure_detected = True

        # Wait for testing to finish on all RAID drives and then print the
        # result.
        for bus_id in bus_ids:
            device = "%s,%s" % (device_type, bus_id)
            if test != "validate":
                try:
                    wait_smartctl_selftest(blockdevice, test, device)
                except (TimeoutExpired, CalledProcessError):
                    failure_detected = True
            try:
                check_smartctl(blockdevice, device)
            except (TimeoutExpired, CalledProcessError):
                failure_detected = True
            if len(bus_ids) > 1:
                print("-" * 80)
    else:
        if test != "validate":
            try:
                run_smartctl_selftest(blockdevice, test)
                wait_smartctl_selftest(blockdevice, test)
            except (TimeoutExpired, CalledProcessError):
                failure_detected = True
        try:
            check_smartctl(blockdevice)
        except (TimeoutExpired, CalledProcessError):
            failure_detected = True

    return not failure_detected


if __name__ == "__main__":
    # Determine the default test based on the script name.
    default_test = "validate"
    for test_name in {"short", "long", "conveyance"}:
        if test_name in sys.argv[0]:
            default_test = test_name
            break

    parser = argparse.ArgumentParser(
        description="SMART Storage Device Test Runner"
    )
    parser.add_argument(
        "-t",
        "--test",
        default=default_test,
        type=str,
        help="The SMART test to run, default %s" % default_test,
    )
    parser.add_argument(
        "blockdevice", help="The blockdevice to test e.g. /dev/sda"
    )
    args = parser.parse_args()

    if not execute_smartctl(args.blockdevice, args.test):
        sys.exit(sys.exit(os.EX_IOERR))
