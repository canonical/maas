# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: start a database shell.

Overrides the default implementation.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = ['Command']

from optparse import make_option
import subprocess

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.core.management.commands import dbshell


class Command(dbshell.Command):
    """Customized "dbshell" command."""

    help = "Interactive psql shell for the MAAS database."

    option_list = BaseCommand.option_list + (
        make_option(
            '--database', default=None, help="Database to connect to."),
        make_option(
            '--installed', '-i', action='store_true', default=False,
            help=(
                "Connect to global, system-installed database.  "
                "Default is to start, and connect to, database in a "
                "development branch.")),
        )

    def handle(self, **options):
        if options.get('installed'):
            # Access the global system-installed MAAS database.
            database = options.get('database')
            if database is None:
                database = 'maasdb'
            try:
                subprocess.check_call(
                    ['sudo', '-u', 'postgres', 'psql', database])
            except subprocess.CalledProcessError:
                # If psql fails to run, it will print a message to stderr.
                # Capturing that can get a little involved; psql might think
                # it was running noninteractively.  So just produce a standard
                # error message, and rely on the stderr output coming from
                # psql itself.
                raise CommandError("psql failed.")
        else:
            # Don't call up to Django's dbshell, because that ends up exec'ing
            # the shell, preventing this from clearing down the fixture.

            # Import fixture here, because installed systems won't have it.
            try:
                from maasserver.testing import database
            except ImportError as e:
                raise ImportError(
                    unicode(e) + "\n"
                    "If this is an installed MAAS, use the --installed "
                    "option.")
            cluster = database.MAASClusterFixture(options.get('database'))
            with cluster:
                cluster.shell(cluster.dbname)
