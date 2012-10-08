# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS command-line interface."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "main",
    ]

import locale
import sys

from bzrlib import osutils
from maascli.parser import prepare_parser


def main(argv=None):
    # Set up the process's locale; this helps bzrlib decode command-line
    # arguments in the next step.
    locale.setlocale(locale.LC_ALL, "")
    if argv is None:
        argv = sys.argv[:1] + osutils.get_unicode_argv()

    parser = prepare_parser(argv)

    # Run, doing polite things with exceptions.
    try:
        options = parser.parse_args(argv[1:])
        options.execute(options)
    except KeyboardInterrupt:
        raise SystemExit(1)
    except StandardError as error:
        parser.error("%s" % error)
