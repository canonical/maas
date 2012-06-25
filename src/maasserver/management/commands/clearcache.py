# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: clear the cache."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Command',
    ]

from optparse import make_option

from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    option_list = BaseCommand.option_list + (
        make_option('--key', dest='username', default=None,
            help="Specify a specific key to delete."),
      )
    help = "Clear the cache (the entire cache or only a specific key)."

    def handle(self, *args, **options):
        key = options.get('key', None)
        if key is None:
            cache.clear()
        else:
            cache.delete(key)
