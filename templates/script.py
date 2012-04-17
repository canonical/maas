#!/usr/bin/env python2.7
# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""..."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type

import argparse

# See http://docs.python.org/release/2.7/library/argparse.html.
argument_parser = argparse.ArgumentParser(description=__doc__)


if __name__ == "__main__":
    args = argument_parser.parse_args()
    print(args)
