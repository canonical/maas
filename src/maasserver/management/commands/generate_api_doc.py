from django.core.management.base import BaseCommand
from maasserver.api import (
    api_doc_title,
    generate_api_doc,
    )


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write('\n'.join([api_doc_title, generate_api_doc()]))
