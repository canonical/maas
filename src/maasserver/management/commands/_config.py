# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: change region controller configuration settings."""


import json
import sys

from django.core.management.base import BaseCommand, CommandError
import formencode
import yaml

from maascli.utils import parse_docstring
from maasserver.config import RegionConfiguration
from provisioningserver.config import ConfigurationOption


def make_option_tuple(name, **kwargs):
    """
    Return a (name, dict) tuple with the dict containing argument options.
    """
    return (name, kwargs)


def p_configuration_option(name, value):
    """Returns True if `name, value` constitutes a configuration option.

    `name` is typically the attribute name from a `Configuration` subclass,
    and `value` is its corresponding class attribute.
    """
    return not name.startswith("_") and (
        isinstance(value, ConfigurationOption) or isinstance(value, property)
    )


def gen_configuration_options():
    """Generate `name, value` tuples of region configuration options."""
    for name, value in vars(RegionConfiguration).items():
        if p_configuration_option(name, value):
            yield name, value


def gen_mutable_configuration_options():
    """Generate `name, value` tuples of region configuration options.

    Only mutable (i.e. settable and resettable) options are yielded.
    """
    for name, option in gen_configuration_options():
        if isinstance(option, ConfigurationOption):
            yield name, option


def option_doc(option):
    """Return only the 'title' line from the option's docstring."""
    title, body = parse_docstring(option.__doc__)
    return title


def gen_configuration_options_for_getting():
    """Generate region configuration options that can be read.

    These options take the form of :class:`optparse.Option` instances, for use
    with Django's management command framework.
    """
    for name, option in sorted(gen_configuration_options()):
        yield make_option_tuple(
            "--" + name.replace("_", "-"),
            action="store_true",
            dest=name,
            default=False,
            help=option_doc(option),
        )


def gen_configuration_options_for_resetting():
    """Generate region configuration options that can be reset.

    These options take the form of :class:`optparse.Option` instances, for use
    with Django's management command framework.
    """
    for name, option in sorted(gen_mutable_configuration_options()):
        yield make_option_tuple(
            "--" + name.replace("_", "-"),
            action="store_true",
            dest=name,
            default=False,
            help=option_doc(option),
        )


def gen_configuration_options_for_setting():
    """Generate region configuration options that can be set.

    These options take the form of :class:`optparse.Option` instances, for use
    with Django's management command framework.
    """
    for name, option in sorted(gen_mutable_configuration_options()):
        yield make_option_tuple(
            "--" + name.replace("_", "-"),
            action="store",
            dest=name,
            default=None,
            help=option_doc(option),
        )


def dump_plain(output):
    """Dump `output`'s value as plain strings to stdout.

    :type output: dict
    """
    for value in output.values():
        print(value)


def dump_json(output):
    """Dump `output` as JSON to stdout.

    :type output: dict
    """
    json.dump(output, sys.stdout)
    # json.dump() does not append a trailing newline.
    print(file=sys.stdout)


def dump_yaml(output):
    """Dump `output` as YAML to stdout.

    :type output: dict
    """
    yaml.safe_dump(output, sys.stdout, default_flow_style=False)


class LocalConfigCommand(BaseCommand):
    """A command class for working with local configuration.

    This must prevent use of the database because the database may not be
    ready for use when this is run, or a user may be providing credentials for
    the database.
    """

    can_import_settings = False
    requires_system_checks = False
    leave_locale_alone = True


class GetCommand(LocalConfigCommand):
    # Do NOT dump to self.stdout; Django does some odd things wrapping stdout,
    # like automatically injecting line breaks, and these break the YAML/JSON
    # output.

    def add_arguments(self, parser):
        super().add_arguments(parser)

        for option_name, kwargs in gen_configuration_options_for_getting():
            parser.add_argument(option_name, **kwargs)

        parser.add_argument(
            "--json",
            action="store_const",
            const=dump_json,
            dest="dump",
            default=dump_yaml,
            help="Output as JSON.",
        )
        parser.add_argument(
            "--yaml",
            action="store_const",
            const=dump_yaml,
            dest="dump",
            default=dump_yaml,
            help="Output as YAML (default).",
        )
        parser.add_argument(
            "--plain",
            action="store_const",
            const=dump_plain,
            dest="dump",
            default=dump_yaml,
            help=(
                "Output as plain strings. The names of the configuration "
                "settings will not be printed and the order is not defined "
                "so this is really only useful when obtaining a single "
                "configuration setting."
            ),
        )

    help = "Get local configuration for the MAAS region controller."

    def handle(self, *args, **options):
        with RegionConfiguration.open() as config:
            output = {
                name: getattr(config, name)
                for name, option in gen_configuration_options()
                if options.get(name)
            }
        dump = options["dump"]
        dump(output)


class ResetCommand(LocalConfigCommand):
    def add_arguments(self, parser):
        super().add_arguments(parser)

        for option_name, kwargs in gen_configuration_options_for_resetting():
            parser.add_argument(option_name, **kwargs)

    help = "Reset local configuration for the MAAS region controller."

    def handle(self, *args, **options):
        with RegionConfiguration.open_for_update() as config:
            for name, option in gen_configuration_options():
                if options.get(name):
                    delattr(config, name)


class SetCommand(LocalConfigCommand):
    help = "Set local configuration for the MAAS region controller."

    def add_arguments(self, parser):
        super().add_arguments(parser)

        for option_name, kwargs in gen_configuration_options_for_setting():
            parser.add_argument(option_name, **kwargs)

    def handle(self, *args, **options):
        with RegionConfiguration.open_for_update() as config:
            for name, option in gen_configuration_options():
                value = options.get(name)
                if value is not None:
                    try:
                        setattr(config, name, value)
                    except formencode.Invalid as error:
                        message = str(error).rstrip(".")
                        raise CommandError(
                            "{}: {}.".format(name.replace("_", "-"), message)
                        )
