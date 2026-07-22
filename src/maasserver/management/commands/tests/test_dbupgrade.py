# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbupgrade` command."""

from contextlib import closing
import os
from subprocess import PIPE, Popen, STDOUT

from postgresfixture import ClusterFixture
from testtools.content import Content, UTF8_TEXT

from maasserver.testing.config import RegionConfigurationFixture
from maastesting import dev_root
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase


def get_plpgsql_function_names(conn):
    """Return the names of PL/pgSQL function names."""
    with closing(conn.cursor()) as cursor:
        cursor.execute(
            "SELECT proname FROM pg_proc, pg_language"
            " WHERE pg_language.oid = pg_proc.prolang"
            "   AND pg_language.lanname = 'plpgsql'"
        )
        return cursor.fetchall()


class TestDBUpgrade(MAASTestCase):
    dbname = "test_maas_dbupgrade"

    def setUp(self):
        """Setup a special database cluster to perform the tests."""
        super().setUp()
        self.datadir = self.useFixture(TempDirectory()).path
        self.cluster = self.useFixture(ClusterFixture(self.datadir))
        self.useFixture(
            RegionConfigurationFixture(
                database_name=self.dbname,
                database_user=None,
                database_pass=None,
                database_host=self.datadir,
            )
        )

    def execute(self, command, env):
        process = Popen(command, stdout=PIPE, stderr=STDOUT, env=env)
        output, _ = process.communicate()
        if output:
            name = f"stdout/err from `{command!r}`"
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
        self.assertEqual(0, process.wait(), "(return code is not zero)")

    def execute_dbupgrade(self):
        env = os.environ.copy()
        env["MAAS_PREVENT_MIGRATIONS"] = "0"
        mra = os.path.join(dev_root, "bin", "maas-region")
        cmd = [
            mra,
            "dbupgrade",
            "--settings",
            "maasserver.djangosettings.settings",
            "--openfga-path",
            os.getcwd() + "/src/maasopenfga/build/",
        ]
        self.execute(cmd, env=env)

    def test_dbupgrade(self):
        """Test ensures that dbupdate works."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade()

    def test_dbupgrade_executes_alembic_migrations(self):
        """Test ensures that a new installation does not run django_migrations but just the alembic ones."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            with closing(conn.cursor()) as cursor:
                # Check that alembic_version is not empty
                cursor.execute("SELECT COUNT(*) FROM alembic_version;")
                alembic_version_count = cursor.fetchone()[0]
                self.assertGreater(
                    alembic_version_count,
                    0,
                    "alembic_version table should not be empty",
                )

    def test_dbupgrade_creates_openfga_schema(self):
        """Test ensures that a new installation creates the openfga schema."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute("""
                    SELECT schema_name
                    FROM information_schema.schemata
                    WHERE schema_name = 'openfga';
                """)
                self.assertIsNotNone(cursor.fetchone())

    def test_dbupgrade_executes_openfga_migrations(self):
        """Test ensures that the openfga migrations have been applied and the initial model has been created."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            with closing(conn.cursor()) as cursor:
                cursor.execute("""
                    SELECT authorization_model_id
                    FROM openfga.authorization_model
                    WHERE authorization_model_id = '00000000000000000000000000';
                """)
                self.assertIsNotNone(cursor.fetchone())

    def test_dbupgrade_installs_plpgsql(self):
        self.cluster.createdb(self.dbname)
        with closing(self.cluster.connect(self.dbname)) as conn:
            function_names = get_plpgsql_function_names(conn)
            self.assertEqual(function_names, [])
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            function_names = get_plpgsql_function_names(conn)
            self.assertNotEqual(function_names, [])
