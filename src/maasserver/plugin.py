# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS Region."""

__all__ = [
    "RegionAllInOneServiceMaker",
    "RegionMasterServiceMaker",
    "RegionWorkerServiceMaker",
]

import os
import signal
import time

from twisted.application.service import IServiceMaker
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python.threadable import isInIOThread
from zope.interface import implementer

from provisioningserver import logger
from provisioningserver.logger import LegacyLogger
from provisioningserver.prometheus.utils import clean_prometheus_dir
from provisioningserver.utils.debug import (
    register_sigusr1_toggle_cprofile,
    register_sigusr2_thread_dump_handler,
)

log = LegacyLogger()

PGSQL_MIN_VERSION = 14


class UnsupportedDBException(Exception):
    """Unsupported PGSQL server version detected"""

    def __init__(self, version: int, *args: object):
        super().__init__(
            f"Unsupported postgresql server version ({version}) detected"
        )


class Options(logger.VerbosityOptions):
    """Command-line options for `regiond`."""


@implementer(IServiceMaker, IPlugin)
class RegionWorkerServiceMaker:
    """Create the worker service for the Twisted plugin."""

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def _set_pdeathsig(self):
        # Worker must die when the the master dies, no exceptions, no hanging
        # around so it must be killed.
        #
        # Sadly the only way to do this in python is to use ctypes. This tells
        # the kernel that when my parent dies to kill me.
        import ctypes

        libc = ctypes.CDLL("libc.so.6")
        libc.prctl(1, signal.SIGKILL)

    def _configureThreads(self):
        from maasserver.utils import threads

        threads.install_default_pool()
        threads.install_database_pool()

    def _configureLogging(self, verbosity: int):
        # Get something going with the logs.
        logger.configure(verbosity, logger.LoggingMode.TWISTD)

    def _configureDjango(self):
        # Some region services use the ORM at class-load time: force Django to
        # load the models first. This is OK to run in the reactor because
        # having Django -- most specifically the ORM -- up and running is a
        # prerequisite of almost everything in the region controller.
        import django

        django.setup()

    def _configurePservSettings(self):
        # Configure the provisioningserver settings based on the Django
        # django settings.
        from django.conf import settings as django_settings

        from provisioningserver import settings

        settings.DEBUG = django_settings.DEBUG

    def _configureReactor(self):
        # Disable all database connections in the reactor.
        from maasserver.utils.orm import disable_all_database_connections

        if isInIOThread():
            disable_all_database_connections()
        else:
            reactor.callFromThread(disable_all_database_connections)

    def _configureCrochet(self):
        # Prevent other libraries from starting the reactor via crochet.
        # In other words, this makes crochet.setup() a no-op.
        import crochet

        crochet.no_setup()

    def _reconfigureLogging(self):
        # Reconfigure the logging based on the debug mode of Django.
        from django.conf import settings

        if settings.DEBUG:
            # In debug mode, force logging to debug mode.
            logger.set_verbosity(3)

            # When not in the developer environment, patch Django to not
            # use the debug cursor. This is needed or Django will store in
            # memory every SQL query made.
            from provisioningserver.config import is_dev_environment

            if not is_dev_environment():
                from django.db.backends.base import base
                from django.db.backends.utils import CursorWrapper

                base.BaseDatabaseWrapper.make_debug_cursor = (
                    lambda self, cursor: CursorWrapper(cursor, self)
                )

    def makeService(self, options):
        """Construct the MAAS Region service."""
        register_sigusr1_toggle_cprofile("regiond-worker")
        register_sigusr2_thread_dump_handler()

        self._set_pdeathsig()
        self._configureThreads()
        self._configureLogging(options["verbosity"])
        self._configureDjango()
        self._configurePservSettings()
        self._configureReactor()
        self._configureCrochet()

        # Reconfigure the logging if required.
        self._reconfigureLogging()

        # Should the import services run in this worker.
        import_services = False
        if os.environ.get("MAAS_REGIOND_RUN_IMPORTER_SERVICE") == "true":
            import_services = True

        # Populate the region's event-loop with services.
        from maasserver import eventloop

        eventloop.loop.populate(master=False, import_services=import_services)

        # Return the eventloop's services to twistd, which will then be
        # responsible for starting them all.
        return eventloop.loop.services


@implementer(IServiceMaker, IPlugin)
class RegionMasterServiceMaker(RegionWorkerServiceMaker):
    """Create the master service for the Twisted plugin."""

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def _ensureConnection(self):
        from django.db import connection

        from maasserver.utils.orm import postgresql_major_version

        # If connection is already made close it.
        if connection.connection is not None:
            connection.close()

        # Loop forever until a connection can be made.
        while True:
            try:
                connection.ensure_connection()

                pg_ver = postgresql_major_version()
                if pg_ver < PGSQL_MIN_VERSION:
                    raise UnsupportedDBException(pg_ver)

            except Exception:
                log.err(
                    _why=(
                        "Error starting: "
                        "Connection to database cannot be established."
                    )
                )
                time.sleep(1)
            else:
                # Connection made, now close it.
                connection.close()
                break

    def makeService(self, options):
        """Construct the MAAS Region service."""
        register_sigusr1_toggle_cprofile("regiond-master")
        register_sigusr2_thread_dump_handler()
        clean_prometheus_dir()

        self._configureThreads()
        self._configureLogging(options["verbosity"])
        self._configureDjango()
        self._configurePservSettings()
        self._configureReactor()
        self._configureCrochet()
        self._ensureConnection()

        # Reconfigure the logging if required.
        self._reconfigureLogging()

        # Populate the region's event-loop with services.
        from maasserver import eventloop

        eventloop.loop.populate(master=True)

        # Return the eventloop's services to twistd, which will then be
        # responsible for starting them all.
        return eventloop.loop.services


@implementer(IServiceMaker, IPlugin)
class RegionAllInOneServiceMaker(RegionMasterServiceMaker):
    """Create the all-in-one service for the Twisted plugin.

    This service runs all the Twisted services in the same process, instead
    of forking the workers.
    """

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def makeService(self, options):
        """Construct the MAAS Region service."""
        register_sigusr1_toggle_cprofile("regiond-all")
        register_sigusr2_thread_dump_handler()

        self._configureThreads()
        self._configureLogging(options["verbosity"])
        self._configureDjango()
        self._configurePservSettings()
        self._configureReactor()
        self._configureCrochet()
        self._ensureConnection()

        # Reconfigure the logging if required.
        self._reconfigureLogging()

        # Populate the region's event-loop with services.
        from maasserver import eventloop

        eventloop.loop.populate(
            master=True, all_in_one=True, import_services=True
        )

        # Return the eventloop's services to twistd, which will then be
        # responsible for starting them all.
        return eventloop.loop.services
