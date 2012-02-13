from django.core.management.base import BaseCommand
from maasserver.api import generate_api_doc


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(generate_api_doc(add_title=True))
