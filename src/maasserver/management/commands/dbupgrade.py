# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Django command: Upgrade MAAS regiond database using both south and django
>1.7 migration system.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from importlib import import_module
import optparse
import os
import shutil
import subprocess
import sys
import tempfile

import django
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import (
    connections,
    DEFAULT_DB_ALIAS,
)

# Modules that required a south migration.
SOUTH_MODULES = [
    "maasserver",
    "metadataserver",
]


class Command(BaseCommand):
    help = "Upgrades database schema for MAAS regiond."
    option_list = BaseCommand.option_list + (
        optparse.make_option(
            '--database', action='store', dest='database',
            default=DEFAULT_DB_ALIAS,
            help=(
                'Nominates a database to synchronize. Defaults to the '
                '"default" database.')),
        optparse.make_option(
            '--always-south', action='store_true', help=(
                'Always run the south migrations even if not required.')),
        # Hidden argument that is not shown to the user. This argument is used
        # internally to call itself again to run the south migrations in a
        # subprocess.
        optparse.make_option(
            '--south', action='store_true', help=optparse.SUPPRESS_HELP),
        # Hidden argument that is not shown to the user. This argument is used
        # internally to call itself again to run the django builtin migrations
        # in a subprocess.
        optparse.make_option(
            '--django', action='store_true', help=optparse.SUPPRESS_HELP),
    )

    @classmethod
    def _path_to_django16_south(cls):
        """Return path to the in-tree django16 and south source code."""
        from maasserver.migrations import south
        path_to_south_dir = os.path.dirname(south.__file__)
        return os.path.join(
            path_to_south_dir, "django16_south.tar.gz")

    @classmethod
    def _extract_django16_south(cls):
        """Extract the django16 and south source code in to a temp path."""
        path_to_tarball = cls._path_to_django16_south()
        tempdir = tempfile.mkdtemp(prefix='maas-upgrade-')
        subprocess.check_call([
            "tar", "zxf", path_to_tarball, "-C", tempdir])
        return tempdir

    @classmethod
    def _south_was_performed(cls, database):
        """Return True if the database had south migrations performed."""
        cursor = connections[database].cursor()
        cursor.execute("SELECT to_regclass('public.south_migrationhistory')")
        output = cursor.fetchone()
        return output[0] == 'south_migrationhistory'

    @classmethod
    def _get_last_db_south_migration(cls, database, app):
        """Return the name of the last south migration in the database for
        the application."""
        cursor = connections[database].cursor()
        cursor.execute(
            "SELECT migration FROM south_migrationhistory "
            "WHERE app_name = %s ORDER BY id DESC LIMIT 1", [app])
        output = cursor.fetchone()
        return output[0]

    @classmethod
    def _get_all_app_south_migrations(cls, app):
        """Return list of all migrations for the given application."""
        migration_module_name = settings.SOUTH_MIGRATION_MODULES[app]
        migration_module = import_module(migration_module_name)
        migration_path = os.path.dirname(migration_module.__file__)
        return sorted([
            os.path.splitext(filename)[0]
            for filename in os.listdir(migration_path)
            if filename != "__init__.py" and filename.endswith(".py")
            ])

    @classmethod
    def _get_last_app_south_migration(cls, app):
        """Return the name of the last migration for the application."""
        return cls._get_all_south_migrations(app)[-1]

    @classmethod
    def _south_migrations_are_complete(cls, database):
        """Return True if all of the south migrations have been performed."""
        for module in SOUTH_MODULES:
            should_have_ran = cls._get_last_south_migration(module)
            last_ran = cls._get_last_ran_south_migration(database, module)
            if should_have_ran != last_ran:
                return False
        return True

    @classmethod
    def _south_needs_to_be_performed(cls, database):
        """Return True if south needs to run on the database."""
        return (
            cls._south_was_performed(database) and
            not cls._south_migrations_are_complete(database))

    @classmethod
    def _rename_piston_to_piston3(cls, database):
        """Rename piston to piston3."""
        cursor = connections[database].cursor()
        cursor.execute(
            "ALTER TABLE piston_consumer RENAME TO piston3_consumer")
        cursor.execute("ALTER TABLE piston_nonce RENAME TO piston3_nonce")
        cursor.execute("ALTER TABLE piston_token RENAME TO piston3_token")

    @classmethod
    def _perform_south_migrations(cls, database, tempdir):
        """Perform the south migrations."""
        env = os.environ.copy()
        env['DJANGO16_SOUTH_MODULES_PATH'] = tempdir
        cmd = [
            sys.argv[0], "dbupgrade", "--database", database,
            "--south",
        ]
        process = subprocess.Popen(cmd, env=env)
        return process.wait()

    @classmethod
    def _perform_django_migrations(cls, database):
        """Perform the django migrations."""
        cmd = [
            sys.argv[0], "dbupgrade", "--database", database,
            "--django",
        ]
        process = subprocess.Popen(cmd)
        return process.wait()

    def handle(self, *args, **options):
        database = options.get('database')
        always_south = options.get('always_south', False)
        run_south = options.get('south', False)
        run_django = options.get('django', False)
        if not run_south and not run_django:
            # Neither south or django provided as an option then this is the
            # main process that will do the initial sync and spawn the
            # subprocesses.

            # Run south migrations only if forced or needed.
            if always_south or self._south_needs_to_be_performed(database):
                # Extract django16 and south for the subprocess.
                tempdir = self._extract_django16_south()

                # Perform south migrations.
                try:
                    rc = self._perform_south_migrations(database, tempdir)
                finally:
                    # Placed in try-finally just to make sure that even if
                    # an exception is raised that the temp directory is
                    # cleaned up.
                    shutil.rmtree(tempdir)
                if rc != 0:
                    sys.exit(rc)

            # Run the django builtin migrations.
            rc = self._perform_django_migrations(database)
            if rc != 0:
                sys.exit(rc)
        elif run_south:
            # Because of maasserver/__init__.py execute_from_command_line we
            # are now running under django 1.6 and south.
            assert django.get_version() == "1.6.6"
            call_command(
                "syncdb", database=database, interactive=False)
            call_command(
                "migrate", "maasserver", database=database, interactive=False)
            call_command(
                "migrate", "metadataserver", database=database,
                interactive=False)
        elif run_django:
            # Piston has been renamed from piston to piston3. If south was ever
            # performed then the tables need to be renamed.
            south_was_performed = self._south_was_performed(database)
            if south_was_performed:
                self._rename_piston_to_piston3(database)

            # Perform the builtin migration faking the initial migrations
            # if south was ever performed.
            call_command(
                "migrate", interactive=False, fake_initial=south_was_performed)
