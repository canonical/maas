from subprocess import check_call

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Stop and delete the local development database cluster."""

    help = "Delete the development database cluster."

    def handle(self, *args, **kwargs):
        if len(args) != 0:
            raise CommandError("Too many arguments.")
        check_call(['bin/maasdb', 'delete-cluster', 'db'])
