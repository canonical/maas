# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbshell` management command."""


import subprocess
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError

from maasserver.management.commands.dbshell import Command as dbshell_command
from maasserver.testing import database as database_module
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestDBShell(MAASServerTestCase):
    def test_runs_installed_cluster_by_default_if_no_dev_fixture(self):
        check_call = self.patch(subprocess, "check_call")
        mock_get_dev_db = self.patch(
            dbshell_command, "get_development_database"
        )
        mock_get_dev_db.return_value = None
        call_command("dbshell")
        self.assertEqual(
            [mock.call(["sudo", "-u", "postgres", "psql", "maasdb"])],
            check_call.mock_calls,
        )

    def test_runs_dev_cluster_by_default_if_dev_fixture_exists(self):
        dbname = factory.make_name("db")
        cluster = self.patch(database_module, "MAASClusterFixture")
        cluster.return_value.dbname = dbname
        call_command("dbshell")
        self.assertEqual(
            [
                mock.call(None),
                mock.call().__enter__(),
                mock.call().shell(dbname),
                mock.call().__exit__(None, None, None),
            ],
            cluster.mock_calls,
        )

    def test_local_run_obeys_database_option_if_given(self):
        dbname = factory.make_name("db")
        cluster = self.patch(database_module, "MAASClusterFixture")
        cluster.return_value.dbname = dbname
        call_command("dbshell", database=dbname)
        self.assertEqual(
            [
                mock.call(dbname),
                mock.call().__enter__(),
                mock.call().shell(dbname),
                mock.call().__exit__(None, None, None),
            ],
            cluster.mock_calls,
        )

    def test_installed_option_connects_to_installed_cluster(self):
        check_call = self.patch(subprocess, "check_call")
        call_command("dbshell", installed=True, database=None)
        self.assertEqual(
            [mock.call(["sudo", "-u", "postgres", "psql", "maasdb"])],
            check_call.mock_calls,
        )

    def test_installed_run_obeys_database_option_if_given(self):
        dbname = factory.make_name("db")
        check_call = self.patch(subprocess, "check_call")
        call_command("dbshell", installed=True, database=dbname)
        self.assertEqual(
            [mock.call(["sudo", "-u", "postgres", "psql", dbname])],
            check_call.mock_calls,
        )

    def test_installed_run_raises_errors_as_CommandError(self):
        self.patch(
            subprocess,
            "check_call",
            mock.MagicMock(
                side_effect=subprocess.CalledProcessError(
                    99, ["command", "line"]
                )
            ),
        )
        error = self.assertRaises(
            CommandError, call_command, "dbshell", installed=True
        )
        self.assertEqual("psql failed.", str(error))
