# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: create a superuser with an empty email."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []


from django.contrib.auth.models import User
from optparse import make_option
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--username', dest='username', default=None,
            help="Specifies the username for the admin."),
        make_option('--password', dest='password', default=None,
            help="Specifies the password for the admin."),
     )
    help = "Used to create an admin with an empty email."

    def handle(self, *args, **options):
        username = options.get('username', None)
        if username is None:
            raise CommandError("You must provide a username with --username.")
        password = options.get('password', None)
        if password is None:
            raise CommandError("You must provide a password with --password.")

        User.objects.db_manager(DEFAULT_DB_ALIAS).create_superuser(
            username, email='', password=password)
