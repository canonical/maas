# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS Region."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "RegionServiceMaker",
]

from itertools import chain
import sys

from provisioningserver.utils.debug import (
    register_sigusr2_thread_dump_handler,
)
from twisted.application.service import IServiceMaker
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.threadable import isInIOThread
from zope.interface import implementer


def serverFromString(description):
    """Lazy import from `provisioningserver.utils.introspect`."""
    from provisioningserver.utils import introspect
    return introspect.serverFromString(description)


class Options(usage.Options):
    """Command line options for the MAAS Region Controller."""

    optParameters = [
        ["introspect", None, None,
         ("Allow introspection, allowing unhindered access to the internals "
          "of MAAS. This should probably only be used for debugging. Supply "
          "an argument in 'endpoint' form; the document 'Getting Connected "
          "with Endpoints' on the Twisted Wiki may help."),
         serverFromString],
    ]


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

    def _checkDatabase(self):
        # Figure out if there are migrations yet to apply.
        try:
            from south import migration, models
            # Limit the applications to `maasserver` and `metadataserver`
            # instead of asking Django for a list of running applications
            # because during testing Django has isolation issues: it returns
            # different lists of running applications depending on what other
            # tests have run, even if the sets of tests requested are from the
            # same application.
            apps = {"maasserver", "metadataserver"}
            migrations = list(chain.from_iterable(
                migration.Migrations(app) for app in apps))
            migrations_applied = list(
                models.MigrationHistory.objects.filter(app_name__in=apps))
            migrations_unapplied = list(
                migration.get_unapplied_migrations(
                    migrations, migrations_applied))
        except SystemExit:
            raise
        except KeyboardInterrupt:
            raise
        except:
            _, error, _ = sys.exc_info()
            raise SystemExit(
                "The MAAS database cannot be used. Please "
                "investigate: %s" % unicode(error).rstrip())
        else:
            if len(migrations_unapplied) > 0:
                raise SystemExit(
                    "The MAAS database schema is not yet fully installed: "
                    "%d migration(s) are missing." % len(migrations_unapplied))
            else:
                # Things look good.
                pass

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

    def _makeIntrospectionService(self, endpoint):
        from provisioningserver.utils import introspect
        introspect_service = (
            introspect.IntrospectionShellService(
                location="region", endpoint=endpoint, namespace={}))
        introspect_service.setName("introspect")
        return introspect_service

    def makeService(self, options):
        """Construct the MAAS Region service."""
        register_sigusr2_thread_dump_handler()

        self._configureThreads()
        self._configureLogging()
        self._configureDjango()
        self._checkDatabase()
        self._configureReactor()
        self._configureCrochet()

        # Populate the region's event-loop with services.
        from maasserver import eventloop
        eventloop.loop.populate()

        if options["introspect"] is not None:
            # Start an introspection (manhole-like) service. Attach it to the
            # eventloop's services so that it shares their lifecycle.
            introspect = self._makeIntrospectionService(options["introspect"])
            introspect.setServiceParent(eventloop.loop.services)

        # Return the eventloop's services to twistd, which will then be
        # responsible for starting them all.
        return eventloop.loop.services
