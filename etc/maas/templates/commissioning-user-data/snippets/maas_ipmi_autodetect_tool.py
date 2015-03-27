#!/usr/bin/python

from __future__ import (
    absolute_import,
    print_function,
    # unicode_literals,
    )

str = None

__metaclass__ = type

import commands
import glob
import re
import subprocess


def detect_ipmi():
    # XXX: andreserl 2013-04-09 bug=1064527: Try to detect if node
    # is a Virtual Machine. If it is, do not try to detect IPMI.
    with open('/proc/cpuinfo', 'r') as cpuinfo:
        for line in cpuinfo:
            if line.startswith('model name') and 'QEMU' in line:
                return (False, None)

    (status, output) = commands.getstatusoutput('ipmi-locate')
    show_re = re.compile('(IPMI\ Version:) (\d\.\d)')
    res = show_re.search(output)
    if res is None:
        found = glob.glob("/dev/ipmi[0-9]")
        if len(found):
            return (True, "UNKNOWN: %s" % " ".join(found))
        return (False, "")
    return (True, res.group(2))


def is_host_moonshot():
    output = subprocess.check_output(['ipmitool', 'raw', '06', '01'])
    # 14 is the code that identifies a machine as a moonshot
    if output.split()[0] == "14":
        return True
    return False


def main():
    # Check whether IPMI exists or not.
    (status, ipmi_version) = detect_ipmi()
    if not status:
        # if False, then failed to detect ipmi
        exit(1)

    if is_host_moonshot():
        print("moonshot")
    else:
        print("ipmi")


if __name__ == '__main__':
    main()
