# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
from optparse import make_option

from django.contrib.auth.models import User
from django.core.management.base import (
    BaseCommand,
    CommandError,
    )
from django.db import DEFAULT_DB_ALIAS


class InconsistentPassword(CommandError):
    """User did not confirm password choice correctly."""


def prompt_for_password():
    """Prompt user for a choice of password, and confirm."""
    password = getpass("Password: ")
    confirm = getpass("Again: ")
    if confirm != password:
        raise InconsistentPassword("Passwords do not match")
    return password


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
            raise CommandError("You must provide a username with --username.")
        password = options.get('password', None)
        if password is None:
            password = prompt_for_password()
        email = options.get('email', None)
        if email is None:
            raise CommandError("You must provide an email with --email.")

        User.objects.db_manager(DEFAULT_DB_ALIAS).create_superuser(
            username, email=email, password=password)
