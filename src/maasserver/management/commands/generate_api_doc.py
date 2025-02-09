# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: generate the API documentation."""

from django.core.management.base import BaseCommand

from maasserver.api.doc_handler import api_doc_title, render_api_docs


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write("\n".join([api_doc_title, render_api_docs()]))
