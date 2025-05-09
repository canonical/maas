# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: create an administrator account."""

from getpass import getpass
import re

from aiohttp import ClientError
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, IntegrityError, transaction

from maascli.init import read_input
from maasserver.enum import KEYS_PROTOCOL_TYPE
from maasserver.management.commands.base import BaseCommandWithConnection


class EmptyUsername(CommandError):
    """User did not provide a username."""


class InconsistentPassword(CommandError):
    """User did not confirm password choice correctly."""


class EmptyEmail(CommandError):
    """User did not provide an email."""


class AlreadyExistingUser(CommandError):
    """A user with the given email already exists."""


class SSHKeysError(CommandError):
    """Error during SSH keys import."""


def read_password(prompt: str):
    while True:
        try:
            data = getpass(prompt)
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


def prompt_for_username() -> str:
    username = read_input("Username: ")
    if not username:
        raise EmptyUsername(
            "You must input a username or provide it with --username."
        )
    return username


def prompt_for_password() -> str:
    """Prompt user for a choice of password, and confirm."""
    password = read_password("Password: ")
    confirm = read_password("Again: ")
    if confirm != password:
        raise InconsistentPassword("Passwords do not match")
    if not confirm and not password:
        raise InconsistentPassword("Passwords cannot be empty")
    return password


def prompt_for_email() -> str:
    """Prompt user for an email."""
    email = read_input("Email: ")
    if not email:
        raise EmptyEmail("You must input an email or provide it with --email")
    return email


def prompt_for_ssh_import() -> str:
    """Prompt user for protocal and user-id to import SSH keys."""
    return read_input("Import SSH keys [] (lp:user-id or gh:user-id): ")


def validate_ssh_import(ssh_import: str):
    """Validate user's SSH import input."""
    if ssh_import.startswith(("lp", "gh")):
        import_regex = re.compile(r"^(?:lp|gh):[\w-]*$")
        match = import_regex.match(ssh_import)
        if match is not None:
            return tuple(match.group().split(":"))
        else:
            raise SSHKeysError(
                "The protocol or user-id entered is not in a correct format. "
                "Your SSH keys will not be imported."
            )
    else:
        protocol = KEYS_PROTOCOL_TYPE.LP
        import_regex = re.compile(r"^[\w-]*$")
        match = import_regex.match(ssh_import)
        if match is not None:
            print(
                "SSH import protocol was not entered.  "
                "Using Launchpad protocol (default)."
            )
            return protocol, match.group()
        else:
            raise SSHKeysError(
                "The input entered is not in a correct format. "
                "Your SSH keys will not be imported."
            )


class Command(BaseCommandWithConnection):
    help = "Create a MAAS administrator account."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", default=None, help="Username for the new account."
        )
        parser.add_argument(
            "--password",
            default=None,
            help="Force a given password instead of prompting.",
        )
        parser.add_argument(
            "--email", default=None, help="Specifies the email for the admin."
        )
        parser.add_argument(
            "--ssh-import",
            default=None,
            help="Import SSH keys from Launchpad (lp:user-id) or "
            "Github (gh:user-id).",
        )

    def handle(self, *args, **options):
        from django.contrib.auth.models import User

        from maasserver.macaroon_auth import external_auth_enabled
        from maasserver.models import SSHKey
        from maasserver.models.sshkey import ImportSSHKeysError

        username = options.get("username")
        password = options.get("password")
        email = options.get("email")
        ssh_import = options.get("ssh_import")
        prompt_ssh_import = False
        if ssh_import is None and (
            username is None or password is None or email is None
        ):
            prompt_ssh_import = True
        if username is None:
            username = prompt_for_username()
        if password is None and not external_auth_enabled():
            password = prompt_for_password()
        if email is None:
            email = prompt_for_email()
        if prompt_ssh_import:
            ssh_import = prompt_for_ssh_import()

        with transaction.atomic():
            try:
                User.objects.db_manager(DEFAULT_DB_ALIAS).create_superuser(
                    username, email=email, password=password
                )
            except IntegrityError:
                raise AlreadyExistingUser(  # noqa: B904
                    "A user with the email %s already exists." % email
                )

            if ssh_import:  # User entered input
                protocol, auth_id = validate_ssh_import(ssh_import)
                user = User.objects.get(username=username)
                try:
                    SSHKey.objects.from_keysource(
                        user=user, protocol=protocol, auth_id=auth_id
                    )
                except (
                    ImportSSHKeysError,
                    ClientError,
                ) as e:
                    raise SSHKeysError(  # noqa: B904
                        "Importing SSH keys failed.\n%s" % e.args[0]
                    )
