# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: generate the API documentation."""

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
from maasserver.api import (
    api_doc_title,
    generate_api_doc,
    )


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write('\n'.join([api_doc_title, generate_api_doc()]))
