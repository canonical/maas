# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Django command: Upgrade MAAS regiond database.
"""


import argparse
import os
import subprocess
import sys
from textwrap import dedent

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connections, DEFAULT_DB_ALIAS

from maasserver.plugin import PGSQL_MIN_VERSION, UnsupportedDBException
from provisioningserver.path import get_path


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

    @classmethod
    def _temporal_migration(cls, database):
        """Run Temporal SQL database migration tool"""

        print("Running Temporal migrations:")
        conn = connections[database]
        conn_params = conn.get_connection_params()

        # Database connection attributes, e.g. host or search_path
        connect_attributes = []

        endpoint = conn_params["host"]

        # endpoint starting with a forward slash ("/"), it is interpreted as
        # a Unix domain socket path rather than a TCP/IP address
        if endpoint.startswith("/"):
            connect_attributes.append(f"host={endpoint}")

            # If the host name starts with @, it is taken as a Unix-domain socket
            # in the abstract namespace (currently supported on Linux and Windows).
            # https://www.postgresql.org/docs/current/libpq-connect.html#LIBPQ-PARAMKEYWORDS
            endpoint = "@"

        def _temporal_sql_tool(args, schema):
            attributes = connect_attributes + [f"search_path={schema}"]

            if conn_params.get("password"):
                password = ["--password", conn_params["password"]]
            else:
                password = []

            if conn_params.get("user"):
                user = ["--user", conn_params["user"]]
            else:
                user = []

            # if port is empty, force set to 5432, otherwise Temporal sets it to 3306
            port = conn_params.get("port", "5432")

            cmd = (
                [
                    get_path("/usr/bin/temporal-sql-tool"),
                    "--plugin",
                    "postgres",
                    "--endpoint",
                    endpoint,
                    "--port",
                    port,
                    "--database",
                    conn_params["database"],
                    "--ca",
                    "&".join(attributes),
                ]
                + user
                + password
                + args
            )

            try:
                subprocess.check_output(cmd, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                print("Failed to apply Temporal migrations")
                print(e.stderr.decode("utf-8"))
                sys.exit(e.returncode)

        schema_path = get_path("/var/lib/maas/temporal/schema")

        temporal_schema_path = os.path.join(
            schema_path, "temporal", "versioned"
        )

        visibility_schema_path = os.path.join(
            schema_path, "visibility", "versioned"
        )

        # This multi-step approach is taken from Temporal auto-setup:
        # https://github.com/temporalio/docker-builds/blob/0e21f3235ec3168d851a6457aa1b1e9c5ac15fc1/docker/auto-setup.sh#L204
        _temporal_sql_tool(
            ["setup-schema", "-v", "0.0"],
            "temporal",
        )

        _temporal_sql_tool(
            ["update-schema", "-d", temporal_schema_path],
            "temporal",
        )

        _temporal_sql_tool(
            ["setup-schema", "-v", "0.0"],
            "temporal_visibility",
        )

        _temporal_sql_tool(
            ["update-schema", "-d", visibility_schema_path],
            "temporal_visibility",
        )

        print("  Applied all migrations.")

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
