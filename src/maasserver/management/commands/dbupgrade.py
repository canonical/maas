# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
Django command: Upgrade MAAS regiond database.
"""

import getpass
from importlib.resources import files
import os
import subprocess
import sys

from alembic import command, config
from django.core.management.base import BaseCommand
from django.db import connections, DEFAULT_DB_ALIAS

from maasserver.plugin import PGSQL_MIN_VERSION, UnsupportedDBException
from maasservicelayer.db import DatabaseConfig
from provisioningserver.path import get_path


def _get_dbname(conn_params: dict) -> str | None:
    """Return the database name from connection parameters.

    Temporal SQL tooling uses ``dbname``, while Django 3.x uses ``database``.
    """
    return conn_params.get("dbname") or conn_params.get("database")


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
            "--openfga-path",
            action="store",
            dest="openfga_path",
            default="/usr/sbin/",
            help=("The path to the openfga migrator binaries."),
        )

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
            dbname = _get_dbname(conn_params)

            sslmode = conn_params.get("sslmode", "prefer")
            cmd = [
                get_path("/usr/bin/temporal-sql-tool"),
                "--plugin",
                "postgres12",
                "--endpoint",
                endpoint,
                "--port",
                port,
                "--database",
                dbname,
            ]
            if sslmode in ("require", "verify-ca", "verify-full"):
                cmd += ["--tls"]
                if sslmode == "require":
                    cmd += ["--tls-disable-host-verification"]
                if conn_params.get("sslcert"):
                    cmd += ["--tls-cert-file", conn_params["sslcert"]]
                    cmd += ["--tls-key-file", conn_params["sslkey"]]
                    if conn_params.get("sslrootcert"):
                        cmd += ["--tls-ca-file", conn_params["sslrootcert"]]
            cmd += ["--ca", "&".join(attributes)]
            cmd += user + password + args

            try:
                subprocess.check_output(cmd, stderr=subprocess.PIPE)
            except subprocess.CalledProcessError as e:
                print("Failed to apply Temporal migrations")
                print(e.stderr.decode("utf-8"))
                sys.exit(e.returncode)

        schema_path = get_path("/var/lib/temporal/schema")

        temporal_schema_path = os.path.join(
            schema_path, "temporal", "versioned"
        )

        visibility_schema_path = os.path.join(
            schema_path, "visibility", "versioned"
        )

        # This multi-step approach is taken from Temporal auto-setup:
        # https://github.com/temporalio/docker-builds/blob/0e21f3235ec3168d851a6457aa1b1e9c5ac15fc1/docker/auto-setup.sh#L204
        setup_temporal_schema, setup_temporal_visibility_schema = False, False
        with conn.cursor() as cursor:
            cursor.execute("SELECT to_regclass('temporal.schema_version')")
            if not cursor.fetchone()[0]:
                setup_temporal_schema = True
            else:
                cursor.execute(
                    "UPDATE temporal.schema_version set db_name = current_database()"
                )

            cursor.execute(
                "SELECT to_regclass('temporal_visibility.schema_version')"
            )
            if not cursor.fetchone()[0]:
                setup_temporal_visibility_schema = True
            else:
                cursor.execute(
                    "UPDATE temporal_visibility.schema_version set db_name = current_database()"
                )

        if setup_temporal_schema:
            _temporal_sql_tool(
                ["setup-schema", "-v", "0.0"],
                "temporal",
            )

        if setup_temporal_visibility_schema:
            _temporal_sql_tool(
                ["setup-schema", "-v", "0.0"],
                "temporal_visibility",
            )

        _temporal_sql_tool(
            ["update-schema", "-d", temporal_schema_path],
            "temporal",
        )

        _temporal_sql_tool(
            ["update-schema", "-d", visibility_schema_path],
            "temporal_visibility",
        )

        print("  All temporal migrations applied.")

    @classmethod
    def _build_postgres_dsn(cls, conn_params, driver, search_path=None):
        # If the user is not set, use the current system user. Otherwise some drivers might crash https://github.com/jackc/pgx/issues/2495
        user = conn_params.get("user") or getpass.getuser()
        password = conn_params.get("password") or ""
        host = conn_params.get("host") or "localhost"
        port = conn_params.get("port")
        dbname = _get_dbname(conn_params)

        auth = f"{user}:{password}@" if password else f"{user}@"

        if host.startswith("/"):  # It's a Unix socket
            connstring = f"{driver}://{auth}localhost/{dbname}?host={host}"
            if search_path:
                connstring = f"{connstring}&search_path={search_path}"
        else:
            port_part = f":{port}" if port else ""
            connstring = f"{driver}://{auth}{host}{port_part}/{dbname}"
            params = []
            if search_path:
                params.append(f"search_path={search_path}")
            if "asyncpg" not in driver:
                sslmode = conn_params.get("sslmode") or "prefer"
                params.append(f"sslmode={sslmode}")
                if sslcert := conn_params.get("sslcert"):
                    params.append(f"sslcert={sslcert}")
                    params.append(f"sslkey={conn_params.get('sslkey', '')}")
                if sslrootcert := conn_params.get("sslrootcert"):
                    params.append(f"sslrootcert={sslrootcert}")
            if params:
                connstring = f"{connstring}?{'&'.join(params)}"
        return connstring

    @classmethod
    def _build_alembic_connect_args(cls, conn_params):
        dbname = _get_dbname(conn_params)
        return {
            "ssl": DatabaseConfig(
                name=dbname,
                host=conn_params.get("host") or "localhost",
                port=conn_params.get("port"),
                username=conn_params.get("user") or "",
                password=conn_params.get("password") or "",
                sslmode=conn_params.get("sslmode") or "prefer",
                sslcert=conn_params.get("sslcert") or "",
                sslkey=conn_params.get("sslkey") or "",
                sslrootcert=conn_params.get("sslrootcert") or "",
            ).build_ssl_param()
        }

    def _openfga_migration(self, openfga_path, database, uri):
        print("Running OpenFGA migrations:")
        conn = connections[database]
        with conn.cursor() as cursor:
            cursor.execute("CREATE SCHEMA IF NOT EXISTS openfga;")

        cmd = [
            get_path(openfga_path + "/maas-openfga-migrator"),
            uri,
        ]

        try:
            subprocess.check_output(cmd, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print("Failed to apply OpenFGA migrations")
            print(e.stderr.decode("utf-8"))
            sys.exit(e.returncode)
        print("  All OpenFGA migrations applied.")

    def _openfga_app_migration(self, openfga_path, uri):
        print("Running OpenFGA model migrations:")
        cmd = [
            get_path(openfga_path + "/maas-openfga-app-migrator"),
            uri,
        ]

        try:
            subprocess.check_output(cmd, stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as e:
            print("Failed to apply OpenFGA App migrations")
            print(e.stderr.decode("utf-8"))
            sys.exit(e.returncode)
        print("  All OpenFGA model migrations applied.")

    def handle(self, *args, **options):
        database = options.get("database")

        # Check database version
        conn = connections[database]
        conn.ensure_connection()
        pg_ver = conn.cursor().connection.server_version
        if pg_ver // 100 < PGSQL_MIN_VERSION:
            raise UnsupportedDBException(pg_ver)

        # When we execute the unit tests we don't have OpenFGA built binaries available at the location where the migrator
        # expects them, so we let the unit tests specify where to find them. We have to run the openfga built-in migrations before the alembic ones because the alembic migrations depend on some of the database structures created by the openfga built-in migrations.
        openfga_path = options.get("openfga_path")
        openfga_dsn = self._build_postgres_dsn(
            conn.get_connection_params(), "postgres", search_path="openfga"
        )
        self._openfga_migration(openfga_path, database, openfga_dsn)

        # Run alembic migrations
        alembic_ini_path = str(
            files("maasservicelayer.db.alembic") / "alembic.ini"
        )
        alembic_cfg = config.Config(alembic_ini_path)
        alembic_cfg.set_main_option("run_migrations", "true")
        conn_params = conn.get_connection_params()
        dsn = self._build_postgres_dsn(conn_params, "postgresql+asyncpg")
        alembic_cfg.set_main_option("sqlalchemy.url", dsn)
        alembic_cfg.attributes["connect_args"] = (
            self._build_alembic_connect_args(conn_params)
        )
        command.upgrade(alembic_cfg, "head")

        # Make sure we're going to see the same database as the migrations
        # have left behind.
        if connections[database].in_atomic_block:
            raise AssertionError(
                "An ongoing transaction may hide changes made "
                "by external processes."
            )

        self._temporal_migration(database)

        openfga_app_dsn = self._build_postgres_dsn(
            conn.get_connection_params(), "postgres"
        )
        self._openfga_app_migration(openfga_path, openfga_app_dsn)
