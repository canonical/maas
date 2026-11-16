# Copyright 2012-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Methods related to initializing a MAAS deployment."""

import argparse
import sys


def deprecated_for(new_option):
    """Return an arparse.Action for deprecating another option.

    It prints out a deprecation message and calls the new option.

    """

    class DeprecatedAction(argparse.Action):
        _new_option = new_option
        _deprecation_message = (
            'Note: "{option_string}" is deprecated and will be removed, '
            'please use "{new_option}" instead.'
        )

        def __init__(self, *args, **kwargs):
            kwargs.setdefault("help", argparse.SUPPRESS)
            kwargs["default"] = argparse.SUPPRESS
            super().__init__(*args, **kwargs)

        def __call__(self, parser, namespace, values, option_string=None):
            action = parser._option_string_actions.get(self._new_option)
            assert action, f'unknown option "{self._new_option}"'
            assert option_string, (
                '"deprecate_for" must be used with optional arguments'
            )
            print(
                self._deprecation_message.format(
                    option_string=option_string, new_option=self._new_option
                ),
                file=sys.stderr,
            )
            option_string = self._new_option
            return action(
                parser, namespace, values, option_string=option_string
            )

    return DeprecatedAction


def add_create_admin_options(parser, suppress_help=False):
    parser.add_argument(
        "--admin-username",
        default=None,
        metavar="USERNAME",
        help=(
            argparse.SUPPRESS
            if suppress_help
            else "Username for the admin account."
        ),
    )
    parser.add_argument(
        "--admin-password",
        default=None,
        metavar="PASSWORD",
        help=(
            argparse.SUPPRESS
            if suppress_help
            else "Force a given admin password instead of prompting."
        ),
    )
    parser.add_argument(
        "--admin-email",
        default=None,
        metavar="EMAIL",
        help=(
            argparse.SUPPRESS
            if suppress_help
            else "Email address for the admin."
        ),
    )
    parser.add_argument(
        "--admin-ssh-import",
        default=None,
        metavar="LP_GH_USERNAME",
        help=(
            argparse.SUPPRESS
            if suppress_help
            else "Import SSH keys from Launchpad (lp:user-id) or "
            "Github (gh:user-id) for the admin."
        ),
    )


def print_msg(msg="", newline=True, stderr=False):
    """Print a message to stdout.

    Flushes the message to ensure its written immediately.
    """
    stream = sys.stderr if stderr else sys.stdout
    print(msg, end=("\n" if newline else ""), flush=True, file=stream)


def read_input(prompt):
    """Reads input from stdin."""
    while True:
        try:
            data = input(prompt)
        except EOFError:
            # Ctrl-d was pressed?
            print()
            continue
        except KeyboardInterrupt:
            print()
            raise SystemExit(1)  # noqa: B904
        else:
            # The assumption is that, since Python 3 return a Unicode string
            # from input(), it has Done The Right Thing with respect to
            # character encoding.
            return data


def prompt_for_choices(prompt, choices, default=None, help_text=None):
    """Prompt requires specific choice answeres.

    If `help_text` is provided the 'help' is added as a choice.
    """
    invalid_msg = "Invalid input, try again"
    if help_text:
        invalid_msg += " or type 'help'"
    invalid_msg += "."
    value = None
    while True:
        value = read_input(prompt)
        if not value:
            if default:
                return default
            else:
                print_msg(invalid_msg)
                print_msg()
        elif value == "help" and help_text:
            print_msg(help_text)
            print_msg()
        elif value not in choices:
            print_msg(invalid_msg)
            print_msg()
        else:
            return value


def prompt_yes_no(message: str) -> bool:
    """Prompts user with a question and returns true if the answer is 'y'"""
    return read_input(message).lower().strip() == "y"
