# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Manage a user's API keys."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []


from optparse import make_option

from apiclient.creds import (
    convert_string_to_tuple,
    convert_tuple_to_string,
    )
import django
from django.contrib.auth.models import User
from django.core.management.base import (
    BaseCommand,
    CommandError,
    )
from django.http import Http404
from maasserver.models.user import get_creds_tuple
from maasserver.utils.orm import get_one


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option(
            '--username', dest='username', default=None,
            help="Specifies the username for the admin."),
        make_option(
            '--generate', action="store_true", dest='generate',
            default=False, help="Generate a new api key."),
        make_option(
            '--delete', dest='delete', default=None,
            help="Delete the supplied api key."),
    )
    help = (
        "Used to manage a user's API keys. Shows existing keys unless "
        "--generate or --delete is passed.")

    def _print_token(self, token):
        """Write `token` to stdout in the standard format."""
        self.stdout.write(convert_tuple_to_string(get_creds_tuple(token)))
        # In Django 1.5+, self.stdout.write() adds a newline character at
        # the end of the message.
        if django.VERSION < (1, 5):
            self.stdout.write('\n')

    def _generate_token(self, user):
        _, token = user.get_profile().create_authorisation_token()
        self._print_token(token)

    def _delete_token(self, user, key_to_delete):
        # Extract the token key from the api key string.
        try:
            creds_tuple = convert_string_to_tuple(key_to_delete)
        except ValueError, e:
            raise CommandError(e)
        _, token_key, _ = creds_tuple
        try:
            user.get_profile().delete_authorisation_token(token_key)
        except Http404:
            raise CommandError("No matching api key found.")

    def handle(self, *args, **options):
        username = options.get('username', None)
        if username is None:
            raise CommandError("You must provide a username with --username.")

        generate = options.get('generate')
        key_to_delete = options.get('delete', None)
        if generate and key_to_delete is not None:
            raise CommandError("Specify one of --generate or --delete.")

        user = get_one(User.objects.filter(username=username))
        if user is None:
            raise CommandError("User does not exist.")

        if generate:
            # Generate a new api key.
            self._generate_token(user)
            return

        elif key_to_delete is not None:
            # Delete an existing api key.
            self._delete_token(user, key_to_delete)
            return

        else:
            # No mutating action requested, so just print existing keys.
            tokens = user.get_profile().get_authorisation_tokens()
            for token in tokens:
                self._print_token(token)
