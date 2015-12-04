# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS Region."""

__all__ = [
    "RegionServiceMaker",
]

from provisioningserver.utils.debug import (
    register_sigusr2_thread_dump_handler,
)
from twisted.application.service import IServiceMaker
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.threadable import isInIOThread
from zope.interface import implementer


class Options(usage.Options):
    """Command line options for the MAAS Region Controller."""


@implementer(IServiceMaker, IPlugin)
class RegionServiceMaker:
    """Create a service for the Twisted plugin."""

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def _configureThreads(self):
        from maasserver.utils import threads
        threads.install_default_pool()
        threads.install_database_pool()

    def _configureLogging(self):
        # Get something going with the logs.
        from provisioningserver import logger
        logger.basicConfig()

    def _configureDjango(self):
        # Some region services use the ORM at class-load time: force Django to
        # load the models first. This is OK to run in the reactor because
        # having Django -- most specifically the ORM -- up and running is a
        # prerequisite of almost everything in the region controller.
        try:
            from django import setup as django_setup
        except ImportError:
            pass  # Django < 1.7
        else:
            django_setup()

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

        self._configureThreads()
        self._configureLogging()
        self._configureDjango()
        self._configureReactor()
        self._configureCrochet()

        # Populate the region's event-loop with services.
        from maasserver import eventloop
        eventloop.loop.populate()

        # Return the eventloop's services to twistd, which will then be
        # responsible for starting them all.
        return eventloop.loop.services
