# Copyright 2013-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: Manage a user's API keys."""


from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.http import Http404

from apiclient.creds import convert_string_to_tuple, convert_tuple_to_string
from maasserver.models.user import get_creds_tuple
from maasserver.utils.orm import get_one


class Command(BaseCommand):
    help = (
        "Used to manage a user's API keys. Shows existing keys unless "
        "--generate or --delete is passed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default=None,
            help="Specifies the username for the admin.",
        )
        parser.add_argument(
            "--generate", action="store_true", help="Generate a new api key."
        )
        parser.add_argument(
            "--delete", default=None, help="Delete the supplied api key."
        )
        parser.add_argument(
            "--update", default=None, help="Update the supplied api key name"
        )
        parser.add_argument(
            "--name",
            default=None,
            dest="api_key_name",
            help="Name of the token. This argument should be passed to "
            "--update or --generate options",
        )
        parser.add_argument(
            "--with-names ",
            dest="with_names",
            action="store_true",
            help="Display tokens with their names.",
        )

    def _print_token(self, token):
        """Write `token` to stdout in the standard format (with names if
        --with-names option is enabled)"""
        if self.display_names:
            self.stdout.write(
                "%s %s"
                % (
                    convert_tuple_to_string(get_creds_tuple(token)),
                    token.consumer.name,
                )
            )
        else:
            self.stdout.write(convert_tuple_to_string(get_creds_tuple(token)))

    def _generate_token(self, user, consumer_name=None):
        _, token = user.userprofile.create_authorisation_token(consumer_name)
        self._print_token(token)

    def _delete_token(self, user, key_to_delete):
        # Extract the token key from the api key string.
        try:
            creds_tuple = convert_string_to_tuple(key_to_delete)
        except ValueError as e:
            raise CommandError(e)
        _, token_key, _ = creds_tuple
        try:
            user.userprofile.delete_authorisation_token(token_key)
        except Http404:
            raise CommandError("No matching api key found.")

    def _update_token(self, user, key_to_update, consumer_name):
        try:
            creds_tuple = convert_string_to_tuple(key_to_update)
        except ValueError as e:
            raise CommandError(e)
        _, token_key, _ = creds_tuple
        try:
            user.userprofile.modify_consumer_name(token_key, consumer_name)
        except Http404:
            raise CommandError("No matching api key found.")

    def handle(self, *args, **options):
        username = options.get("username", None)
        if username is None:
            raise CommandError("You must provide a username with --username.")

        generate = options.get("generate")
        key_to_delete = options.get("delete", None)
        key_to_update = options.get("update", None)
        consumer_name = options.get("api_key_name", None)
        self.display_names = options.get("with_names", None)

        if generate and key_to_delete is not None:
            raise CommandError("Specify one of --generate or --delete.")

        if generate and key_to_update is not None:
            raise CommandError("Specify one of --generate or --update.")

        if key_to_delete and key_to_update is not None:
            raise CommandError("Specify one of --delete or --update.")

        if key_to_update is not None and consumer_name is None:
            raise CommandError("Should specify new name for the updated key .")

        user = get_one(User.objects.filter(username=username))

        if user is None:
            raise CommandError("User does not exist.")

        if generate:
            # Generate a new api key.
            self._generate_token(user, consumer_name)
            return

        elif key_to_delete is not None:
            # Delete an existing api key.
            self._delete_token(user, key_to_delete)
            return

        elif key_to_update is not None:
            # Update an existing key name.
            self._update_token(user, key_to_update, consumer_name)
            return

        else:
            # No mutating action requested, so just print existing keys.
            tokens = user.userprofile.get_authorisation_tokens()
            for token in tokens:
                self._print_token(token)
