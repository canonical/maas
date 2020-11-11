# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: generate sample data."""


from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = "Populate the database with semi-random sample data."

    def handle(self, *args, **options):
        try:
            from maasserver.testing import sampledata
        except ImportError:
            print(
                "Sample data generation is available only in development "
                "and test environments.",
                file=self.stderr,
            )
            raise SystemExit(1)
        else:
            sampledata.populate()
