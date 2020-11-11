# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Django command: db_vacuum_lobjects (vacuums the large objects in the DB)."""


import subprocess
from textwrap import dedent

from django.core.management.base import BaseCommand, CommandError


def _make_vacuum_command(database):
    """Return an appropriate command for performing a full vacuum on the
    database, which is necessary to remove stale (deleted) large objects.
    :param database: The database to vacuum.
    :return: a command in list format, suitable to pass to a subprocess
    """
    command = [
        "sudo",
        # Note: we had intended to use the 'maas' user for this, but this
        # doesn't end up reducing the size of the database. Also, the console
        # outputs dozens of warnings. I assume this is the key warning:
        # WARNING:  skipping "pg_largeobject" ---
        #     only superuser or database owner can vacuum it
        "-u",
        "postgres",
        "vacuumdb",
        # Note: we had intended to restrict this to only the
        # 'maasserver_largefile' table, which contains the references to our
        # large files, but this doesn't end up reducing the size of the
        # database. It turns out vacuuming the 'pg_largeobject' table does
        # the trick, but only the database administrator can access it.
        # And we risk breaking this functionality if postgresql changes its
        # behavior. On the other hand, the locking implications are less scary,
        # and the vacuum takes considerably less time if we restrict it to
        # this single table.
        "-t",
        "pg_largeobject",
        "--full",
        "-d",
        database,
    ]
    return command


class Command(BaseCommand):
    """Vacuums the table of large objects, which can grow very large over time
    (especially if the user is using boot images from the "daily" stream).
    """

    help = dedent(
        "Vacuums large objects from the database. (This is occasionally "
        "needed if repeated updates of MAAS boot images have caused the "
        "database to grow in size.)"
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--database",
            default=None,
            help="Database to connect to. (default: the database found in "
            "the options file, or 'maasdb' if not found.)",
        )

    def handle(self, **options):
        # Access the global system-installed MAAS database.
        database = options.get("database")
        if database is None:
            database = "maasdb"
        try:
            command = _make_vacuum_command(database)
            subprocess.check_call(command)
        except subprocess.CalledProcessError:
            raise CommandError("Error while vacuuming the database.")
        else:
            print("Database vacuumed successfully.")
