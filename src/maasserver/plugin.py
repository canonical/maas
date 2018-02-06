# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS Region."""

__all__ = [
    "RegionAllInOneServiceMaker",
    "RegionMasterServiceMaker",
    "RegionWorkerServiceMaker",
]

import signal
import time

from provisioningserver import logger
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.debug import (
    register_sigusr2_thread_dump_handler,
)
from twisted.application.service import IServiceMaker
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python.threadable import isInIOThread
from zope.interface import implementer


log = LegacyLogger()


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

    def makeService(self, options):
        """Construct the MAAS Region service."""
        register_sigusr2_thread_dump_handler()

        self._set_pdeathsig()
        self._configureThreads()
        self._configureLogging(options["verbosity"])
        self._configureDjango()
        self._configureReactor()
        self._configureCrochet()

        # Populate the region's event-loop with services.
        from maasserver import eventloop
        eventloop.loop.populate(master=False)

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
        # If connection is already made close it.
        from django.db import connection
        if connection.connection is not None:
            connection.close()

        # Loop forever until a connection can be made.
        while True:
            try:
                connection.ensure_connection()
            except Exception:
                log.err(_why=(
                    "Error starting: "
                    "Connection to database cannot be established."))
                time.sleep(1)
            else:
                # Connection made, now close it.
                connection.close()
                break

    def makeService(self, options):
        """Construct the MAAS Region service."""
        register_sigusr2_thread_dump_handler()

        self._configureThreads()
        self._configureLogging(options["verbosity"])
        self._configureDjango()
        self._configureReactor()
        self._configureCrochet()
        self._ensureConnection()

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
        register_sigusr2_thread_dump_handler()

        self._configureThreads()
        self._configureLogging(options["verbosity"])
        self._configureDjango()
        self._configureReactor()
        self._configureCrochet()
        self._ensureConnection()

        # Populate the region's event-loop with services.
        from maasserver import eventloop
        eventloop.loop.populate(master=True, all_in_one=True)

        # Return the eventloop's services to twistd, which will then be
        # responsible for starting them all.
        return eventloop.loop.services
