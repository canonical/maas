# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the dbupgrade works."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
from pipes import quote
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)

from maastesting import root
from maastesting.testcase import MAASTestCase
from postgresfixture import ClusterFixture
from testtools.content import (
    Content,
    UTF8_TEXT,
)


class TestDBUpgrade(MAASTestCase):

    def setup_database(self):
        """Setup a special database in the development environment to perform
        the tests."""
        self.cluster = self.useFixture(ClusterFixture("db", preserve=True))

    def execute(self, command, env=os.environ):
        process = Popen(command, stdout=PIPE, stderr=STDOUT, env=env)
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % " ".join(map(quote, command))
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
        self.assertEqual(0, process.wait(), "(return code is not zero)")

    def execute_dbupgrade(self, always_south=False):
        env = os.environ.copy()
        env["DEV_DB_NAME"] = "test_maas_dbupgrade"
        env["MAAS_PREVENT_MIGRATIONS"] = "0"
        mra = os.path.join(root, "bin", "maas-region-admin")
        cmd = [mra, "dbupgrade"]
        if always_south:
            cmd.append("--always-south")
        self.execute(cmd, env=env)

    def test_dbupgrade_with_always_south(self):
        """Test ensures that dbupdate always works by performing the south
        migrations first. This ensures that nothing in the MAAS code prevents
        upgrades from pre-MAAS 2.0 versions from upgrading to 2.0+."""
        self.setup_database()
        self.cluster.dropdb("test_maas_dbupgrade")
        self.cluster.createdb("test_maas_dbupgrade")
        self.execute_dbupgrade(always_south=True)

    def test_dbupgrade_without_south(self):
        """Test ensures that dbupdate works without performing the south
        migrations first."""
        self.setup_database()
        self.cluster.dropdb("test_maas_dbupgrade")
        self.cluster.createdb("test_maas_dbupgrade")
        self.execute_dbupgrade(always_south=False)
