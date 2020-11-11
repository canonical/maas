# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: start a database shell.

Overrides the default implementation.
"""


import subprocess

from django.core.management.base import CommandError
from django.core.management.commands import dbshell


class Command(dbshell.Command):
    """Customized "dbshell" command."""

    help = "Interactive psql shell for the MAAS database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--database", default=None, help="Database to connect to."
        )
        parser.add_argument(
            "--dev",
            action="store_true",
            default=False,
            help=(
                "Connect to a development database database. "
                "Default is to start, and connect to, a system-installed "
                "database."
            ),
        )
        parser.add_argument(
            "--installed",
            "-i",
            action="store_true",
            default=False,
            help=(
                "Connect to global, system-installed database. "
                "This is the default, unless a development environment is "
                "detected."
            ),
        )

    def get_development_database(self):
        database = None
        try:
            # Installed systems won't have this fixture.
            from maasserver.testing import database
        except ImportError:
            pass

        return database

    def handle(self, **options):
        database_fixture = self.get_development_database()
        if options.get("dev"):
            if database_fixture is None:
                raise CommandError("No development database found.")
        elif options.get("installed"):
            # If we have a development database but the user passed in
            # --installed, we need to use the system database instead.
            # So clear it out if we found one.
            database_fixture = None

        if database_fixture is None:
            # Access the global system-installed MAAS database.
            database_name = options.get("database")
            if database_name is None:
                database_name = "maasdb"
            try:
                subprocess.check_call(
                    ["sudo", "-u", "postgres", "psql", database_name]
                )
            except subprocess.CalledProcessError:
                # If psql fails to run, it will print a message to stderr.
                # Capturing that can get a little involved; psql might think
                # it was running noninteractively.  So just produce a standard
                # error message, and rely on the stderr output coming from
                # psql itself.
                raise CommandError("psql failed.")
        else:
            print("Using development database.")

            # Don't call up to Django's dbshell, because that ends up exec'ing
            # the shell, preventing this from clearing down the fixture.
            cluster = database_fixture.MAASClusterFixture(
                options.get("database")
            )
            with cluster:
                cluster.shell(cluster.dbname)
