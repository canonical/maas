# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbupgrade` command."""

__all__ = []

from contextlib import closing
import os
from pipes import quote
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)

from maasserver.testing.config import RegionConfigurationFixture
from maastesting import root
from maastesting.fixtures import TempDirectory
from maastesting.testcase import MAASTestCase
from postgresfixture import ClusterFixture
from testtools.content import (
    Content,
    UTF8_TEXT,
)
from testtools.matchers import (
    HasLength,
    Not,
)


def get_plpgsql_function_names(conn):
    """Return the names of PL/pgSQL function names."""
    with closing(conn.cursor()) as cursor:
        cursor.execute(
            "SELECT proname FROM pg_proc, pg_language"
            " WHERE pg_language.oid = pg_proc.prolang"
            "   AND pg_language.lanname = 'plpgsql'")
        return cursor.fetchall()


class TestDBUpgrade(MAASTestCase):

    dbname = "test_maas_dbupgrade"

    def setUp(self):
        """Setup a special database cluster to perform the tests."""
        super(TestDBUpgrade, self).setUp()
        self.datadir = self.useFixture(TempDirectory()).path
        self.cluster = self.useFixture(ClusterFixture(self.datadir))
        self.useFixture(RegionConfigurationFixture(
            database_name=self.dbname, database_user=None,
            database_pass=None, database_host=self.datadir))

    def execute(self, command, env):
        process = Popen(command, stdout=PIPE, stderr=STDOUT, env=env)
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % " ".join(map(quote, command))
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
        self.assertEqual(0, process.wait(), "(return code is not zero)")

    def execute_dbupgrade(self, always_south=False):
        env = os.environ.copy()
        env["MAAS_PREVENT_MIGRATIONS"] = "0"
        mra = os.path.join(root, "bin", "maas-region")
        cmd = [
            mra, "dbupgrade", "--settings",
            "maasserver.djangosettings.settings",
        ]
        if always_south:
            cmd.append("--always-south")
        self.execute(cmd, env=env)

    def test_dbupgrade_with_always_south(self):
        """Test ensures that dbupdate always works by performing the south
        migrations first. This ensures that nothing in the MAAS code prevents
        upgrades from pre-MAAS 2.0 versions from upgrading to 2.0+."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade(always_south=True)

    def test_dbupgrade_without_south(self):
        """Test ensures that dbupdate works without performing the south
        migrations first."""
        self.cluster.createdb(self.dbname)
        self.execute_dbupgrade(always_south=False)

    def test_dbupgrade_installs_plpgsql(self):
        self.cluster.createdb(self.dbname)
        with closing(self.cluster.connect(self.dbname)) as conn:
            function_names = get_plpgsql_function_names(conn)
            self.assertThat(function_names, HasLength(0))
        self.execute_dbupgrade(always_south=False)
        with closing(self.cluster.connect(self.dbname)) as conn:
            function_names = get_plpgsql_function_names(conn)
            self.assertThat(function_names, Not(HasLength(0)))
