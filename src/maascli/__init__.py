# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS command-line interface."""

__all__ = [
    "main",
    ]

import sys

from maascli.parser import prepare_parser


def main(argv=sys.argv):
    # If no arguments have been passed be helpful and point out --help.
    if len(argv) == 1:
        sys.stderr.write(
            "Error: no arguments given.\n"
            "Run %s --help for usage details.\n"
            % argv[0])
        raise SystemExit(2)

    parser = prepare_parser(argv)

    # Run, doing polite things with exceptions.
    try:
        options = parser.parse_args(argv[1:])
        options.execute(options)
    except KeyboardInterrupt:
        raise SystemExit(1)
    except Exception as error:
        parser.error("%s" % error)


try:
    import maasfascist
    maasfascist  # Silence lint.
except ImportError:
    pass
