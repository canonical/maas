# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""CLI management commands."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'register_cli_commands',
    ]

from textwrap import fill

from apiclient.creds import convert_tuple_to_string
from maascli.api import fetch_api_description
from maascli.auth import obtain_credentials
from maascli.command import Command
from maascli.config import ProfileConfig
from maascli.utils import (
    api_url,
    parse_docstring,
    safe_name,
    )


class cmd_login(Command):
    """Log in to a remote API, and remember its description and credentials.

    If credentials are not provided on the command-line, they will be prompted
    for interactively.
    """

    def __init__(self, parser):
        super(cmd_login, self).__init__(parser)
        parser.add_argument(
            "profile_name", metavar="profile-name", help=(
                "The name with which you will later refer to this remote "
                "server and credentials within this tool."
                ))
        parser.add_argument(
            "url", type=api_url, help=(
                "The URL of the remote API, e.g. http://example.com/MAAS/ "
                "or http://example.com/MAAS/api/1.0/ if you wish to specify "
                "the API version."))
        parser.add_argument(
            "credentials", nargs="?", default=None, help=(
                "The credentials, also known as the API key, for the "
                "remote MAAS server. These can be found in the user "
                "preferences page in the web UI; they take the form of "
                "a long random-looking string composed of three parts, "
                "separated by colons."
                ))
        parser.add_argument(
            '-k', '--insecure', action='store_true', help=(
                "Disable SSL certificate check"), default=False)
        parser.set_defaults(credentials=None)

    def __call__(self, options):
        # Try and obtain credentials interactively if they're not given, or
        # read them from stdin if they're specified as "-".
        credentials = obtain_credentials(options.credentials)
        # Get description of remote API.
        description = fetch_api_description(options.url, options.insecure)
        # Save the config.
        profile_name = options.profile_name
        with ProfileConfig.open() as config:
            config[profile_name] = {
                "credentials": credentials,
                "description": description,
                "name": profile_name,
                "url": options.url,
                }
            profile = config[profile_name]
        self.print_whats_next(profile)

    @staticmethod
    def print_whats_next(profile):
        """Explain what to do next."""
        what_next = [
            "You are now logged in to the MAAS server at {url} "
            "with the profile name '{name}'.",
            "For help with the available commands, try:",
            "  maas-cli {name} --help",
            ]
        print()
        for message in what_next:
            message = message.format(**profile)
            print(fill(message))
            print()


class cmd_refresh(Command):
    """Refresh the API descriptions of all profiles.

    This retrieves the latest version of the help information for each
    profile.  Use it to update your maas-cli client's information after an
    upgrade to the MAAS server.
    """

    def __call__(self, options):
        with ProfileConfig.open() as config:
            for profile_name in config:
                profile = config[profile_name]
                url = profile["url"]
                profile["description"] = fetch_api_description(url)
                config[profile_name] = profile


class cmd_logout(Command):
    """Log out of a remote API, purging any stored credentials.

    This will remove the given profile from your maas-cli client.  You can
    re-create it by logging in again later.
    """

    def __init__(self, parser):
        super(cmd_logout, self).__init__(parser)
        parser.add_argument(
            "profile_name", metavar="profile-name", help=(
                "The name with which a remote server and its credentials "
                "are referred to within this tool."
                ))

    def __call__(self, options):
        with ProfileConfig.open() as config:
            del config[options.profile_name]


class cmd_list(Command):
    """List remote APIs that have been logged-in to."""

    def __call__(self, options):
        with ProfileConfig.open() as config:
            for profile_name in config:
                profile = config[profile_name]
                url = profile["url"]
                creds = profile["credentials"]
                if creds is None:
                    print(profile_name, url)
                else:
                    creds = convert_tuple_to_string(creds)
                    print(profile_name, url, creds)


commands = {
    'login': cmd_login,
    'logout': cmd_logout,
    'list': cmd_list,
    'refresh': cmd_refresh,
}


def register_cli_commands(parser):
    """Register the CLI's meta-subcommands on `parser`."""
    for name, command in commands.items():
        help_title, help_body = parse_docstring(command)
        command_parser = parser.subparsers.add_parser(
            safe_name(name), help=help_title, description=help_title,
            epilog=help_body)
        command_parser.set_defaults(execute=command(command_parser))
