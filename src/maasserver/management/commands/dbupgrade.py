# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Django command: Upgrade MAAS regiond database.
"""


import argparse
from textwrap import dedent

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections, DEFAULT_DB_ALIAS

from maasserver.plugin import PGSQL_MIN_VERSION, UnsupportedDBException


class Command(BaseCommand):
    help = "Upgrades database schema for MAAS regiond."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--database",
            action="store",
            dest="database",
            default=DEFAULT_DB_ALIAS,
            help=(
                "Nominates a database to synchronize. Defaults to the "
                '"default" database.'
            ),
        )
        parser.add_argument(
            "--internal-no-triggers",
            action="store_true",
            dest="no_triggers",
            help=argparse.SUPPRESS,
        )

    @classmethod
    def _perform_trigger_installation(cls, database):
        """Register all PL/pgSQL functions and triggers.

        :attention: `database` argument is not used!
        """
        from maasserver import triggers

        triggers.register_all_triggers()

    @classmethod
    def _get_all_triggers(cls, database):
        """Return list of all triggers in the database."""
        with connections[database].cursor() as cursor:
            cursor.execute(
                dedent(
                    """\
                SELECT tgname::text, pg_class.relname
                FROM pg_trigger, pg_class
                WHERE pg_trigger.tgrelid = pg_class.oid AND (
                    pg_class.relname LIKE 'maasserver_%' OR
                    pg_class.relname LIKE 'metadataserver_%' OR
                    pg_class.relname LIKE 'auth_%') AND
                    NOT pg_trigger.tgisinternal
                ORDER BY tgname::text;
                """
                )
            )
            return [(row[0], row[1]) for row in cursor.fetchall()]

    @classmethod
    def _drop_all_triggers(cls, database):
        """Remove all of the triggers that MAAS has created previously."""
        triggers = cls._get_all_triggers(database)
        with connections[database].cursor() as cursor:
            for trigger_name, table in triggers:
                cursor.execute(
                    f"DROP TRIGGER IF EXISTS {trigger_name} ON {table};"
                )

    @classmethod
    def _drop_all_views(cls, database):
        """Register all PL/pgSQL views.

        :attention: `database` argument is not used!
        """
        from maasserver import dbviews

        dbviews.drop_all_views()

    @classmethod
    def _perform_view_installation(cls, database):
        """Register all PL/pgSQL views.

        :attention: `database` argument is not used!
        """
        from maasserver import dbviews

        dbviews.register_all_views()

    def handle(self, *args, **options):
        database = options.get("database")
        no_triggers = options.get("no_triggers")

        # Check database version
        conn = connections[database]
        conn.ensure_connection()
        pg_ver = conn.cursor().connection.server_version
        if pg_ver // 100 < PGSQL_MIN_VERSION:
            raise UnsupportedDBException(pg_ver)

        # First, drop any views that may already exist. We don't want views
        # that that depend on a particular schema to prevent schema
        # changes due to the dependency. The views will be recreated at the
        # end of this process.
        self._drop_all_views(database)

        # Remove all of the trigger that MAAS uses before performing the
        # migrations. This ensures that no triggers are ran during the
        # migrations and that only the updated triggers are installed in
        # the database.
        self._drop_all_triggers(database)

        # Run the django builtin migrations.
        call_command(
            "migrate", interactive=False, verbosity=options.get("verbosity")
        )

        # Make sure we're going to see the same database as the migrations
        # have left behind.
        if connections[database].in_atomic_block:
            raise AssertionError(
                "An ongoing transaction may hide changes made "
                "by external processes."
            )

        # Install all database functions, triggers, and views. This is
        # idempotent, so we run it at the end of every database upgrade.
        if not no_triggers:
            self._perform_trigger_installation(database)
        self._perform_view_installation(database)
