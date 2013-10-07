# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Arguments parser for `maascli`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'prepare_parser',
    ]

import argparse

from maascli import api
from maascli.cli import register_cli_commands
from maascli.utils import parse_docstring


class ArgumentParser(argparse.ArgumentParser):
    """Specialisation of argparse's parser with better support for subparsers.

    Specifically, the one-shot `add_subparsers` call is disabled, replaced by
    a lazily evaluated `subparsers` property.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault(
            "formatter_class", argparse.RawDescriptionHelpFormatter)
        super(ArgumentParser, self).__init__(*args, **kwargs)

    def add_subparsers(self):
        raise NotImplementedError(
            "add_subparsers has been disabled")

    @property
    def subparsers(self):
        try:
            return self.__subparsers
        except AttributeError:
            parent = super(ArgumentParser, self)
            self.__subparsers = parent.add_subparsers(title="drill down")
            self.__subparsers.metavar = "COMMAND"
            return self.__subparsers


def get_profile_option(argv):
    """Parse the `--profile` option in `argv`; ignore the rest."""
    # Create a specialized parser just to extract this one option.
    # If we call parse_known_args on the real arguments parser, the
    # --help option will do its work and cause the process to exit
    # before we can even add the sub-parsers that the user may be asking
    # for help about.
    specialized_parser = ArgumentParser(add_help=False)
    specialized_parser.add_argument('--profile', metavar='PROFILE')
    provisional_options = specialized_parser.parse_known_args(argv)[0]
    return provisional_options.profile


def prepare_parser(argv):
    """Create and populate an arguments parser for the maascli command."""
    help_title, help_body = parse_docstring(api)
    parser = ArgumentParser(
        description=help_body, prog=argv[0],
        epilog="http://maas.ubuntu.com/")
    register_cli_commands(parser)
    api.register_api_commands(parser)
    return parser
