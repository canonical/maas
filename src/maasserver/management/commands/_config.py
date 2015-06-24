# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: change region controller configuration settings."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    "GetCommand",
    "ResetCommand",
    "SetCommand",
]

from itertools import chain
from optparse import make_option
import sys

from django.core.management.base import BaseCommand
from maasserver.config import RegionConfiguration
from provisioningserver.config import ConfigurationOption
import yaml


def p_configuration_option(name, value):
    """Returns True if `name, value` constitutes a configuration option.

    `name` is typically the attribute name from a `Configuration` subclass,
    and `value` is its corresponding class attribute.
    """
    return (
        not name.startswith("_") and (
            isinstance(value, ConfigurationOption) or
            isinstance(value, property)
        )
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


def gen_configuration_options_for_getting():
    """Generate region configuration options that can be read.

    These options take the form of :class:`optparse.Option` instances, for use
    with Django's management command framework.
    """
    for name, option in sorted(gen_configuration_options()):
        yield make_option(
            "--" + name.replace("_", "-"), action="store_true", dest=name,
            default=False, help=option.__doc__)


def gen_configuration_options_for_resetting():
    """Generate region configuration options that can be reset.

    These options take the form of :class:`optparse.Option` instances, for use
    with Django's management command framework.
    """
    for name, option in sorted(gen_mutable_configuration_options()):
        yield make_option(
            "--" + name.replace("_", "-"), action="store_true", dest=name,
            default=False, help=option.__doc__)


def gen_configuration_options_for_setting():
    """Generate region configuration options that can be set.

    These options take the form of :class:`optparse.Option` instances, for use
    with Django's management command framework.
    """
    for name, option in sorted(gen_mutable_configuration_options()):
        yield make_option(
            "--" + name.replace("_", "-"), action="store", dest=name,
            default=None, help=option.__doc__)


class GetCommand(BaseCommand):

    option_list = tuple(chain(
        BaseCommand.option_list,
        gen_configuration_options_for_getting(),
    ))

    help = "Get local configuration for the MAAS region controller."

    def handle(self, *args, **options):
        with RegionConfiguration.open() as config:
            output = {
                name: getattr(config, name)
                for name, option in gen_configuration_options()
                if options.get(name)
            }
        # Do NOT dump to self.stdout; Django does some odd things wrapping
        # stdout, like automatically injecting line breaks, and these break
        # the YAML output.
        yaml.safe_dump(output, stream=sys.stdout, default_flow_style=False)


class ResetCommand(BaseCommand):

    option_list = tuple(chain(
        BaseCommand.option_list,
        gen_configuration_options_for_resetting(),
    ))

    help = "Reset local configuration for the MAAS region controller."

    def handle(self, *args, **options):
        with RegionConfiguration.open() as config:
            for name, option in gen_configuration_options():
                if options.get(name):
                    delattr(config, name)


class SetCommand(BaseCommand):

    option_list = tuple(chain(
        BaseCommand.option_list,
        gen_configuration_options_for_setting(),
    ))

    help = "Set local configuration for the MAAS region controller."

    def handle(self, *args, **options):
        with RegionConfiguration.open() as config:
            for name, option in gen_configuration_options():
                value = options.get(name)
                if value is not None:
                    setattr(config, name, value)
