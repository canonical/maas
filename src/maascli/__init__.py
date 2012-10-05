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

import argparse
import locale
import sys

from bzrlib import osutils
from maascli.api import (
    register_api_commands,
    register_cli_commands,
    )
from maascli.utils import parse_docstring


class ArgumentParser(argparse.ArgumentParser):
    """Specialisation of argparse's parser with better support for subparsers.

    Specifically, the one-shot `add_subparsers` call is disabled, replaced by
    a lazily evaluated `subparsers` property.
    """

    def add_subparsers(self):
        raise NotImplementedError(
            "add_subparsers has been disabled")

    @property
    def subparsers(self):
        try:
            return self.__subparsers
        except AttributeError:
            parent = super(ArgumentParser, self)
            self.__subparsers = parent.add_subparsers(title="commands")
            return self.__subparsers


def main(argv=None):
    # Set up the process's locale; this helps bzrlib decode command-line
    # arguments in the next step.
    locale.setlocale(locale.LC_ALL, "")
    if argv is None:
        argv = sys.argv[:1] + osutils.get_unicode_argv()

    module = __import__('maascli.api', fromlist=True)
    help_title, help_body = parse_docstring(module)
    parser = ArgumentParser(
        description=help_body, prog=argv[0],
        epilog="http://maas.ubuntu.com/")
    register_cli_commands(parser)
    register_api_commands(parser)

    # Run, doing polite things with exceptions.
    try:
        options = parser.parse_args(argv[1:])
        options.execute(options)
    except KeyboardInterrupt:
        raise SystemExit(1)
    except StandardError as error:
        parser.error("%s" % error)
