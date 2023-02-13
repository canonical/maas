# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
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


def create_trigger_to_delete(conn, namespace):
    with closing(conn.cursor()) as cursor:
        cursor.execute(
            "CREATE TABLE %s__test_table(id integer NOT NULL);" % namespace
        )
        cursor.execute(
            "CREATE FUNCTION test_table_procedure() "
            "RETURNS trigger AS $$ "
            "BEGIN RETURN NEW; END; "
            "$$ LANGUAGE plpgsql;"
        )
        cursor.execute(
            "CREATE TRIGGER test_table_trigger BEFORE INSERT "
            "ON %s__test_table FOR EACH ROW "
            "EXECUTE PROCEDURE test_table_procedure();" % namespace
        )
    return "%s__test_table" % namespace


def get_all_triggers(conn):
    with closing(conn.cursor()) as cursor:
        cursor.execute(
            "SELECT tgname::text "
            "FROM pg_trigger, pg_class "
            "WHERE NOT pg_trigger.tgisinternal;"
        )
        return [row[0] for row in cursor.fetchall()]


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
        ]
        self.execute(cmd, env=env)

    def test_dbupgrade(self):
        """Test ensures that dbupdate works."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade()

    def test_dbupgrade_installs_plpgsql(self):
        self.cluster.createdb(self.dbname)
        with closing(self.cluster.connect(self.dbname)) as conn:
            function_names = get_plpgsql_function_names(conn)
            self.assertEqual(function_names, [])
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            function_names = get_plpgsql_function_names(conn)
            self.assertNotEqual(function_names, [])

    def test_dbupgrade_removes_maasserver_triggers(self):
        self.cluster.createdb(self.dbname)
        with closing(self.cluster.connect(self.dbname)) as conn:
            trigger_name = create_trigger_to_delete(conn, "maasserver")
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            triggers = get_all_triggers(conn)
            self.assertNotIn(trigger_name, triggers)

    def test_dbupgrade_removes_metadataserver_triggers(self):
        self.cluster.createdb(self.dbname)
        with closing(self.cluster.connect(self.dbname)) as conn:
            trigger_name = create_trigger_to_delete(conn, "metadataserver")
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            triggers = get_all_triggers(conn)
            self.assertNotIn(trigger_name, triggers)

    def test_dbupgrade_removes_auth_triggers(self):
        self.cluster.createdb(self.dbname)
        with closing(self.cluster.connect(self.dbname)) as conn:
            trigger_name = create_trigger_to_delete(conn, "auth")
        self.execute_dbupgrade()
        with closing(self.cluster.connect(self.dbname)) as conn:
            triggers = get_all_triggers(conn)
            self.assertNotIn(trigger_name, triggers)
