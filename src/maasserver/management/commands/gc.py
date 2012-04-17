# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom django command: garabge-collect."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Command',
    ]


from django.core.management.base import BaseCommand
from maasserver.models import FileStorage


class Command(BaseCommand):
    def handle(self, *args, **options):
        FileStorage.objects.collect_garbage()
