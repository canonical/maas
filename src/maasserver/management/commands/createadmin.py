# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: create an administrator account."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from getpass import getpass
from locale import getpreferredencoding
from optparse import make_option

from django.contrib.auth.models import User
from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.db import DEFAULT_DB_ALIAS


class EmptyUsername(CommandError):
    """User did not provide a username."""


class InconsistentPassword(CommandError):
    """User did not confirm password choice correctly."""


class EmptyEmail(CommandError):
    """User did not provide an email."""


def read_input(prompt):
    while True:
        try:
            data = raw_input(prompt)
        except EOFError:
            # Ctrl-d was pressed?
            print()
            continue
        except KeyboardInterrupt:
            print()
            raise SystemExit(1)
        else:
            encoding = getpreferredencoding()
            return data.decode(encoding)


def read_password(prompt):
    while True:
        try:
            data = getpass(prompt)
        except EOFError:
            # Ctrl-d was pressed?
            print()
            continue
        except KeyboardInterrupt:
            print()
            raise SystemExit(1)
        else:
            encoding = getpreferredencoding()
            return data.decode(encoding)


def prompt_for_username():
    username = read_input("Username: ")
    if not username:
        raise EmptyUsername("You must input a username or "
                            "provide it with --username.")
    return username


def prompt_for_password():
    """Prompt user for a choice of password, and confirm."""
    password = read_password("Password: ")
    confirm = read_password("Again: ")
    if confirm != password:
        raise InconsistentPassword("Passwords do not match")
    if not confirm and not password:
        raise InconsistentPassword("Passwords cannot be empty")
    return password


def prompt_for_email():
    """Prompt user for an email."""
    email = read_input("Email: ")
    if not email:
        raise EmptyEmail("You must input an email or provide it with --email")
    return email


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--username', dest='username', default=None,
            help="Username for the new account."),
        make_option(
            '--password', dest='password', default=None,
            help="Force a given password instead of prompting."),
        make_option(
            '--email', dest='email', default=None,
            help="Specifies the email for the admin."),
    )
    help = "Create a MAAS administrator account."

    def handle(self, *args, **options):
        username = options.get('username', None)
        if username is None:
            username = prompt_for_username()
        password = options.get('password', None)
        if password is None:
            password = prompt_for_password()
        email = options.get('email', None)
        if email is None:
            email = prompt_for_email()

        User.objects.db_manager(DEFAULT_DB_ALIAS).create_superuser(
            username, email=email, password=password)
