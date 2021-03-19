# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS command-line interface."""


import os
import sys

from maascli.parser import prepare_parser


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
    snap_setup()

    if len(argv) == 1:
        sys.stderr.write(
            "Error: no arguments given.\n"
            "Run %s --help for usage details.\n" % argv[0]
        )
        raise SystemExit(2)

    parser = prepare_parser(argv)

    try:
        options = parser.parse_args(argv[1:])
        if hasattr(options, "execute"):
            options.execute(options)
        else:
            # This mimics the error behaviour provided by argparse 1.1 from
            # PyPI (which differs from argparse 1.1 in the standard library).
            parser.error("too few arguments")
    except KeyboardInterrupt:
        raise SystemExit(1)
    except SystemExit:
        raise  # Pass-through.
    except Exception as error:
        show = getattr(error, "always_show", False)
        if options.debug or show:
            raise
        else:
            # Note: this will call sys.exit() when finished.
            parser.error("%s" % error)
