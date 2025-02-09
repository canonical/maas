# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS command-line interface."""

import os
import sys

from maascli.parser import get_deepest_subparser, prepare_parser


def snap_setup():
    if "SNAP" in os.environ:
        os.environ.update(
            {
                "DJANGO_SETTINGS_MODULE": "maasserver.djangosettings.snap",
                "MAAS_PATH": os.environ["SNAP"],
                "MAAS_ROOT": os.environ["SNAP_DATA"],
                "MAAS_DATA": os.path.join(os.environ["SNAP_COMMON"], "maas"),
                "MAAS_REGION_CONFIG": os.path.join(
                    os.environ["SNAP_DATA"], "regiond.conf"
                ),
            }
        )


def main(argv=sys.argv):
    # If no arguments have been passed be helpful and point out --help.
    verbose_errors = "MAAS_CLI_VERBOSE_ERRORS" in os.environ

    snap_setup()

    parser = prepare_parser(argv)

    try:
        options = parser.parse_args(argv[1:])
        if hasattr(options, "execute"):
            options.execute(options)
        else:
            sub_parser = get_deepest_subparser(parser, argv[1:])
            # This mimics the error behaviour provided by argparse 1.1 from
            # PyPI (which differs from argparse 1.1 in the standard library).
            sub_parser.error("too few arguments")
    except KeyboardInterrupt:
        raise SystemExit(1)  # noqa: B904
    except Exception as error:
        show = getattr(error, "always_show", False)
        if options.debug or show or verbose_errors:
            raise
        else:
            # Note: this will call sys.exit() when finished.
            parser.error("%s" % error)
