from django.core.management.base import BaseCommand
from maasserver.api import docs


class Command(BaseCommand):

    def handle(self, *args, **options):
        messages = ['MaaS API\n========\n\n']
        for doc in docs:
            for method in doc.get_methods():
                messages.append(
                    "%s %s\n  %s\n\n" % (
                        method.http_name, doc.resource_uri_template,
                        method.doc))
        self.stdout.write(''.join(messages))
