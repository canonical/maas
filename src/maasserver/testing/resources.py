# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Resources for testing the MAAS region application."""


from itertools import count
import os
from pathlib import Path
import re
from sys import __stderr__
from textwrap import dedent

from postgresfixture import ClusterFixture
import psycopg2
from psycopg2.errorcodes import DUPLICATE_DATABASE
from testresources import TestResourceManager

here = Path(__file__).parent


# Set `MAAS_DEBUG_RESOURCES` to anything in the calling environment to
# activate some debugging help for the code in this module.
if os.environ.get("MAAS_DEBUG_RESOURCES") is None:

    def debug(message, **args):
        """Throw away all messages."""


else:

    def debug(message, **args):
        """Write a debug message to stderr, delimiting for visibility."""
        args = {
            name: value() if callable(value) else value
            for name, value in args.items()
        }
        print(
            "<< " + message.format(**args) + " >>", file=__stderr__, flush=True
        )


class DatabaseClusterManager(TestResourceManager):
    """Resource manager for a PostgreSQL cluster."""

    setUpCost = 3
    testDownCost = 2

    def make(self, dependencies):
        cluster = ClusterFixture("db", preserve=True)
        cluster.create()
        postgres_path = Path(cluster.datadir)
        postgres_conf = postgres_path / "postgresql.conf"
        postgres_speed_conf = postgres_path / "postgresql.conf.speed"
        if "postgresql.conf.speed" not in postgres_conf.read_text():
            with postgres_conf.open("a") as fh:
                fh.write("include = 'postgresql.conf.speed'\n")
            with postgres_speed_conf.open("w") as fh:
                fh.write(
                    dedent(
                        """\
                    fsync = off
                    full_page_writes = off
                    synchronous_commit = off
                    """
                    )
                )
        cluster.setUp()
        return cluster

    def clean(self, cluster):
        cluster.cleanUp()


class DjangoDatabases(list):
    """A list of Django database settings dicts.

    This is required instead of a plain list so that `testresources` can set
    instance attributes to match the database's dependencies, for example
    `cluster`.
    """


class DjangoPristineDatabaseManager(TestResourceManager):
    """Resource manager for pristine Django databases."""

    resources = (("cluster", DatabaseClusterManager()),)

    setUpCost = 25
    tearDownCost = 1

    def make(self, dependencies):
        cluster = dependencies["cluster"]
        with cluster.lock.exclusive:
            return self._make(cluster)

    def _make(self, cluster):
        # Ensure that Django is initialised.
        import django

        django.setup()

        # Import other modules without risk of toy throwing from Django.
        from django.conf import settings
        from django.core.management import call_command

        from maasserver import dbviews, triggers

        # For each database, create a ${name}_test database.
        databases = DjangoDatabases(
            database
            for database in settings.DATABASES.values()
            if database["HOST"] == cluster.datadir
        )

        created = set()
        with cluster.connect() as conn:
            with conn.cursor() as cursor:
                for database in databases:
                    dbname = database["NAME"] + "_test"
                    stmt = "CREATE DATABASE %s" % dbname
                    try:
                        cursor.execute(stmt)
                    except psycopg2.ProgrammingError as error:
                        if error.pgcode != DUPLICATE_DATABASE:
                            raise
                    else:
                        created.add(dbname)
                        debug(
                            "Created {dbname}; statement: {stmt}",
                            dbname=dbname,
                            stmt=stmt,
                        )
                    database["NAME"] = dbname

        # Attempt to populate these databases from a dumped database script.
        # This is *much* faster than falling back on Django's migrations.
        for database in databases:
            dbname = database["NAME"]
            if dbname in created:
                initial = here.joinpath("initial.%s.sql" % dbname)
                if initial.is_file():
                    cluster.execute(
                        "psql",
                        "--quiet",
                        "--single-transaction",
                        "--set=ON_ERROR_STOP=1",
                        "--dbname",
                        dbname,
                        "--output",
                        os.devnull,
                        "--file",
                        str(initial),
                    )

        # First, drop any views that may already exist. We don't want views
        # that that depend on a particular schema to prevent schema changes
        # due to the dependency. The views will be recreated at the end of
        # this process.
        dbviews.drop_all_views()

        # Apply all current migrations. We use `migrate` here instead of
        # `dbupgrade` because we don't need everything that the latter
        # provides, and, more importantly, we need it to run in-process so
        # that it sees the effects of our settings changes.
        call_command("migrate", interactive=False)

        # Install all database functions, triggers, and views.
        triggers.register_all_triggers()
        dbviews.register_all_views()

        # Ensure that there are no sessions from Django.
        close_all_connections()

        return databases

    def clean(self, databases):
        close_all_connections()
        for database in databases:
            dbname = database["NAME"]
            assert dbname.endswith("_test")
            database["NAME"] = dbname[:-5]


def close_all_connections():
    from django.db import connections

    for conn in connections.all():
        conn.close()


class DjangoDatabasesManager(TestResourceManager):
    """Resource manager for a Django database used for a test.

    Since it's hard to determine whether a database has been modified,
    this manager assumes that it has and mark it as dirty by default.

    Tests that know that the database hasn't been modified can either
    pass in the assume_dirty=False when creating the manager, or set the
    dirty attribute.
    """

    resources = (("templates", DjangoPristineDatabaseManager()),)

    def __init__(self, assume_dirty=True):
        super().__init__()
        self._count = count(1)
        self.dirty = assume_dirty

    def make(self, dependencies):
        databases = dependencies["templates"]
        clusterlock = databases.cluster.lock
        with databases.cluster.connect() as conn:
            with conn.cursor() as cursor:
                for database in databases:
                    template = database["NAME"]
                    dbname = "%s_%d_%d" % (
                        template,
                        os.getpid(),
                        next(self._count),
                    )
                    stmt = "CREATE DATABASE {} WITH TEMPLATE {}".format(
                        dbname,
                        template,
                    )
                    # Create the database with a shared lock to the cluster to
                    # avoid racing a DjangoPristineDatabaseManager.make in a
                    # concurrently running test process.
                    with clusterlock.shared:
                        cursor.execute(stmt)
                    debug(
                        "Created {dbname}; statement: {stmt}",
                        dbname=dbname,
                        stmt=stmt,
                    )
                    database["NAME"] = dbname
        return databases

    def clean(self, databases):
        close_all_connections()
        with databases.cluster.connect() as conn:
            with conn.cursor() as cursor:
                for database in databases:
                    dbname = database["NAME"]
                    template = re.search(r"^(.+)_\d+_\d+$", dbname).group(1)
                    self._stopOtherActivity(cursor, dbname)
                    self._dropDatabase(cursor, dbname)
                    database["NAME"] = template

    @staticmethod
    def _stopOtherActivity(cursor, dbname):
        """Terminate other connections to the given database."""
        cursor.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE pid != pg_backend_pid() AND datname = %s",
            [dbname],
        )
        count = sum((1 if success else 0) for [success] in cursor.fetchall())
        debug(
            "Killed {count} other backends in {dbname}",
            count=count,
            dbname=dbname,
        )

    @staticmethod
    def _dropDatabase(cursor, dbname):
        """Drop the given database."""
        stmt = "DROP DATABASE %s" % dbname
        cursor.execute(stmt)
        debug("Dropped {dbname}; statement: {stmt}", dbname=dbname, stmt=stmt)

    def isDirty(self):
        return self.dirty
