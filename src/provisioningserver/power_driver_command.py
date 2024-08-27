# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import argparse
import sys
from textwrap import dedent

from twisted.internet.defer import ensureDeferred
from twisted.internet.task import react

# This import causes asyncioreactor to be installed
from provisioningserver.drivers.power.registry import PowerDriverRegistry


def _create_subparser(driver_settings, parser):
    """
    Add the relevant CLI arguments specific to each power drivers subparser
    """

    for setting in driver_settings:
        arg_name = setting["name"].replace("_", "-")

        action = "store"
        if setting["choices"]:
            choices = [c[0] for c in setting["choices"]]
            if setting["field_type"] == "multiple_choice":
                action = "append"
        else:
            choices = None

        parser.add_argument(
            f"--{arg_name}",
            dest=setting["name"],
            help=setting["label"],
            required=setting["required"],
            choices=choices,
            action=action,
        )


def _collect_context(driver_settings, args):
    """
    Each driver has a unique set of CLI arguments. Populate and return a dict
    with the arguements that this driver expects.
    """
    return {
        setting["name"]: getattr(args, setting["name"])
        for setting in driver_settings
        if hasattr(args, setting["name"])
    }


def add_arguments(parser):
    parser.description = dedent(
        """\
        The maas-power command line tool allows you to directly interact with
        the maas supported power drivers.
        """
    )
    parser.add_argument(
        "command",
        help="Power driver command.",
        choices=["status", "on", "cycle", "off"],
    )

    # NOTE: In python 3.7 and above required=True can be passed to add_subparsers.
    #       To replicate the behaviour in earlier versions we need to provide a
    #       dest and manually change required.
    subparsers = parser.add_subparsers(dest="driver")
    subparsers.required = True

    for name, driver in PowerDriverRegistry:
        sub = subparsers.add_parser(name, help=driver.description)
        _create_subparser(driver.settings, sub)


def _parse_args(argv):
    parser = argparse.ArgumentParser()
    add_arguments(parser)
    return parser.parse_args(argv)


async def _run(reactor, args, driver_registry=PowerDriverRegistry):
    command = args.command
    driver = driver_registry[args.driver]
    context = _collect_context(driver.settings, args)

    if command == "on":
        await driver.on(None, context)
    elif command == "cycle":
        await driver.cycle(None, context)
    elif command == "off":
        await driver.off(None, context)
    elif command == "set-boot-order" and driver.can_set_boot_order:
        order = []
        if hasattr(args, "order"):
            order = args.order.split(",")
        await driver.set_boot_order(None, context, order)

    # Always show the status, which covers the 'status' command option and
    # gives the user feedback for any other commands.
    status = await driver.query(None, context)

    # Output machine status
    print(status)
    return status


def run(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    args = _parse_args(argv)

    react(
        lambda *args, **kwargs: ensureDeferred(_run(*args, **kwargs)), [args]
    )
