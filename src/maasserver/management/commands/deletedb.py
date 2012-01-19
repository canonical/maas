# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import print_function

from subprocess import check_call

from django.core.management.base import (
    BaseCommand,
    CommandError,
    )


"""Django command: stop and delete the local database cluster."""

__metaclass__ = type
__all__ = ['Command']


class Command(BaseCommand):
    """Stop and delete the local development database cluster."""

    help = "Delete the development database cluster."

    def handle(self, *args, **kwargs):
        if len(args) != 0:
            raise CommandError("Too many arguments.")
        check_call(['bin/maasdb', 'delete-cluster', 'db'])
