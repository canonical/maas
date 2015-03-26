# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper to start the Protractor environment to run MAAS JS E2E tests."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

import os
import signal
from subprocess import Popen
import sys
import time
import traceback

from django.conf import settings
from django.core.management import call_command
from django.db import DEFAULT_DB_ALIAS
from django.test.runner import setup_databases
from fixtures import (
    EnvironmentVariableFixture,
    Fixture,
)
from maastesting.fixtures import (
    ChromiumWebDriverFixture,
    DisplayFixture,
)
from postgresfixture import ClusterFixture
from testtools.monkey import patch
from twisted.scripts import twistd


class ServiceError(Exception):
    """Raised when failure to start a service."""


def redirect_to_devnull():
    """Redirect all input and output to /dev/null."""
    os.setsid()
    null = os.open(os.devnull, os.O_RDWR)
    os.dup2(null, 0)
    os.dup2(null, 1)
    os.dup2(null, 2)
    os.close(null)


class MAASRegionServiceFixture(Fixture):
    """Starts and stops the MAAS region service.

    This process is forked to spawn regiond where it will run a different port
    and connect to the testing database instead of the development database.
    This will isolate this test from the development environment, allowing
    them to run at the same time.
    """

    FIXTURE = "src/maastesting/protractor/fixture.yaml"

    def __init__(self):
        self.verbosity = 1
        self.interactive = False

    def setUp(self):
        """Start the regiond service."""
        super(MAASRegionServiceFixture, self).setUp()
        # Force django DEBUG false.
        self.addCleanup(patch(settings, "DEBUG", False))

        # Create a database in the PostgreSQL cluster for each database
        # connection configured in Django"s settings that points to the same
        # datadir.
        cluster = ClusterFixture("db", preserve=True)
        self.useFixture(cluster)
        for database in settings.DATABASES.values():
            if database["HOST"] == cluster.datadir:
                cluster.createdb(database["NAME"])

        # Setup the database for testing. This is so the database is isolated
        # only for this testing.
        self.setup_databases()
        self.addCleanup(self.teardown_databases)

        # Fork the process to have regiond run in its own process.
        twistd_pid = os.fork()
        if twistd_pid == 0:
            # Redirect all output to /dev/null
            redirect_to_devnull()

            # Add command line options to start twistd.
            sys.argv[1:] = [
                "--nodaemon",
                "--pidfile", "",
                "maas-regiond",
                ]

            # Change the DEFAULT_PORT so it can run along side of the
            # development regiond.
            from maasserver import eventloop
            patch(eventloop, "DEFAULT_PORT", 5253)

            # Start twistd.
            try:
                twistd.run()
            except:
                traceback.print_exc()
                os._exit(2)
            finally:
                os._exit(0)
        else:
            # Add cleanup to stop the twistd service.
            self.addCleanup(self.stop_twistd, twistd_pid)

            # Check that the child process is still running after a few
            # seconds. This makes sure that everything started okay and it
            # is still running.
            time.sleep(2)
            try:
                os.kill(twistd_pid, 0)
            except OSError:
                # Not running.
                raise ServiceError(
                    "Failed to start regiond. Check that another test is "
                    "not running at the same time.")

    def stop_twistd(self, twistd_pid):
        """Stop the regiond service."""
        try:
            os.kill(twistd_pid, signal.SIGINT)
            _, return_code = os.waitpid(twistd_pid, 0)
            if return_code != 0:
                print("WARN: regiond didn't stop cleanly (%d)" % return_code)
        except OSError:
            print("WARN: regiond already died.")

    def setup_databases(self):
        """Setup the test databases."""
        self._old_config = setup_databases(self.verbosity, self.interactive)

        # Load the fixture into the database.
        call_command(
            "loaddata", self.FIXTURE,
            verbosity=self.verbosity, database=DEFAULT_DB_ALIAS,
            skip_validation=True)

    def teardown_databases(self):
        """Teardown the test databases."""
        old_names, mirrors = self._old_config
        for connection, old_name, destroy in old_names:
            if destroy:
                connection.creation.destroy_test_db(old_name, self.verbosity)


class MAASClusterServiceFixture(Fixture):
    """Starts and stops the MAAS cluster service."""

    MAAS_URL = "http://0.0.0.0:5253/MAAS/"
    CLUSTER_UUID = "adfd3977-f251-4f2c-8d61-745dbd690bf2"
    CONFIG_FILE = "src/maastesting/protractor.yaml"

    def setUp(self):
        """Start the clusterd service."""
        super(MAASClusterServiceFixture, self).setUp()
        self.useFixture(EnvironmentVariableFixture(
            "MAAS_URL", self.MAAS_URL))
        self.useFixture(EnvironmentVariableFixture(
            "CLUSTER_UUID", self.CLUSTER_UUID))

        # Fork the process to have clusterd run in its own process.
        twistd_pid = os.fork()
        if twistd_pid == 0:
            # Redirect all output to /dev/null
            redirect_to_devnull()

            # Add command line options to start twistd.
            sys.argv[1:] = [
                "--nodaemon",
                "--pidfile", "",
                "maas-clusterd",
                "--config-file",
                self.CONFIG_FILE,
                ]

            # Start twistd.
            try:
                twistd.run()
            except:
                traceback.print_exc()
                os._exit(2)
            finally:
                os._exit(0)
        else:
            # Add cleanup to stop the twistd service.
            self.addCleanup(self.stop_twistd, twistd_pid)

            # Check that the child process is still running after a few
            # seconds. This makes sure that everything started okay and it
            # is still running.
            time.sleep(2)
            try:
                os.kill(twistd_pid, 0)
            except OSError:
                # Not running.
                raise ServiceError(
                    "Failed to start clusterd. Check that another test is "
                    "not running at the same time.")

    def stop_twistd(self, twistd_pid):
        """Stop the clusterd service."""
        try:
            os.kill(twistd_pid, signal.SIGINT)
            _, return_code = os.waitpid(twistd_pid, 0)
            if return_code != 0:
                print("WARN: clusterd didn't stop cleanly (%d)" % return_code)
        except OSError:
            print("WARN: clusterd already died.")


def run_protractor():
    """Start Protractor with the MAAS JS E2E testing configuration.

    1. Start regiond.
    2. Start clusterd.
    3. Start xvfb.
    4. Start chromium webdriver.
    5. Run protractor.
    6. Stop chromium webdriver.
    7. Stop xvfb.
    8. Stop clusterd.
    9. Stop regiond.
    """
    with MAASRegionServiceFixture(), MAASClusterServiceFixture():
        with DisplayFixture(), ChromiumWebDriverFixture():
            protractor = Popen((
                "bin/protractor",
                "src/maastesting/protractor/protractor.conf.js"))
            protractor_exit = protractor.wait()
    sys.exit(protractor_exit)
