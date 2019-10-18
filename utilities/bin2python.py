#!/usr/bin/env python3

# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Convert the binary content of the standard input stream to a Python string.

Output should be suitable for use in unit tests, after slight format
adjustments.
"""

from pprint import pprint
import sys

in_bytes = sys.stdin.buffer.read()
pprint(in_bytes, width=76)
