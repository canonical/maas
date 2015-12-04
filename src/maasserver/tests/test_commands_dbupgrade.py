# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbupgrade` management command."""

__all__ = []

import datetime
import subprocess
import sys
from textwrap import dedent

from django.core.management import call_command
from django.db import connection
from maasserver.management.commands import dbupgrade as dbupgrade_module
from maasserver.management.commands.dbupgrade import (
    Command as dbupgrade_command,
)
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from testtools.matchers import (
    EndsWith,
    Equals,
    MatchesListwise,
    StartsWith,
)


class TestDBUpgrade(MAASServerTestCase):

    def patch_subprocess(self, rc=0):
        popen = self.patch_autospec(subprocess, "Popen")
        popen.return_value.__enter__.return_value = popen.return_value
        popen.return_value.wait.return_value = rc
        return popen

    def make_south_history(self):
        cursor = connection.cursor()
        cursor.execute(dedent("""\
            CREATE SEQUENCE south_migrationhistory_id_seq;
            CREATE TABLE south_migrationhistory (
                id integer PRIMARY KEY
                    DEFAULT nextval('south_migrationhistory_id_seq'),
                app_name varchar(255) NOT NULL,
                migration varchar(255) NOT NULL,
                applied timestamptz NOT NULL
            );
        """))

    def insert_migration_into_history(self, app, migration):
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO south_migrationhistory(app_name, migration, applied) "
            "VALUES(%s,%s,%s)", [app, migration, datetime.datetime.now()])

    def assertCalledTar(self, mock, call=0):
        path = dbupgrade_command._path_to_django16_south_maas19()
        call = mock.call_args_list[call][0][0]
        self.assertThat(call, MatchesListwise([
            Equals('tar'),
            Equals('zxf'),
            Equals(path),
            Equals('-C'),
            StartsWith('/tmp/maas-upgrade-'),
        ]))

    def assertCalledSouth(self, mock, database="default", call=1):
        call = mock.call_args_list[call]
        self.assertThat(call[0][0], MatchesListwise([
            Equals("python2.7"),
            EndsWith("migrate.py"),
            Equals(database),
        ]))

    def assertCalledDjango(
            self, mock, database="default", call=2):
        call = mock.call_args_list[call]
        cmds = [
            Equals(sys.argv[0]),
            Equals('dbupgrade'),
            Equals("--database"),
            Equals(database),
            Equals("--django"),
        ]
        self.assertThat(call[0][0], MatchesListwise(cmds))

    def test_always_runs_south_when_always_south(self):
        popen = self.patch_subprocess()
        call_command('dbupgrade', always_south=True)
        self.assertCalledTar(popen)
        self.assertCalledSouth(popen)
        self.assertCalledDjango(popen)

    def test_doesnt_run_south_when_not_always_south(self):
        popen = self.patch_subprocess()
        call_command('dbupgrade', always_south=False)
        self.assertCalledDjango(popen, call=0)

    def test_runs_south_if_south_table_exists(self):
        popen = self.patch_subprocess()
        self.make_south_history()
        call_command('dbupgrade', always_south=True)
        self.assertCalledTar(popen)
        self.assertCalledSouth(popen)
        self.assertCalledDjango(popen)

    def test_runs_south_if_missing_maassever_last_migration(self):
        popen = self.patch_subprocess()
        self.make_south_history()
        self.insert_migration_into_history(
            "maasserver",
            dbupgrade_command._get_all_app_south_migrations("maasserver")[-2])
        self.insert_migration_into_history(
            "metadataserver",
            dbupgrade_command._get_all_app_south_migrations(
                "metadataserver")[-1])
        call_command('dbupgrade', always_south=True)
        self.assertCalledTar(popen)
        self.assertCalledSouth(popen)
        self.assertCalledDjango(popen)

    def test_runs_south_if_missing_metadataserver_last_migration(self):
        popen = self.patch_subprocess()
        self.make_south_history()
        self.insert_migration_into_history(
            "maasserver",
            dbupgrade_command._get_all_app_south_migrations("maasserver")[-1])
        self.insert_migration_into_history(
            "metadataserver",
            dbupgrade_command._get_all_app_south_migrations(
                "metadataserver")[-2])
        call_command('dbupgrade', always_south=True)
        self.assertCalledTar(popen)
        self.assertCalledSouth(popen)
        self.assertCalledDjango(popen)

    def test_django_run_renames_piston_tables_if_south_ran_before(self):
        self.patch(
            dbupgrade_command, "_south_was_performed").return_value = True
        mock_rename = self.patch(
            dbupgrade_command, "_rename_piston_to_piston3")
        mock_call = self.patch(dbupgrade_module, "call_command")
        call_command('dbupgrade', django=True)
        self.assertThat(mock_rename, MockCalledOnceWith("default"))
        self.assertThat(
            mock_call, MockCalledOnceWith(
                "migrate", interactive=False, fake_initial=True))

    def test_django_doesnt_rename_piston_tables_if_south_not_ran_before(self):
        self.patch(
            dbupgrade_command, "_south_was_performed").return_value = False
        mock_rename = self.patch(
            dbupgrade_command, "_rename_piston_to_piston3")
        mock_call = self.patch(dbupgrade_module, "call_command")
        call_command('dbupgrade', django=True)
        self.assertThat(mock_rename, MockNotCalled())
        self.assertThat(
            mock_call, MockCalledOnceWith(
                "migrate", interactive=False, fake_initial=False))
