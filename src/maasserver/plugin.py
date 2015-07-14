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


# The maximum number of threads used by the default twisted thread pool.
# This value is a trade-off between a small value (such as the default: 10)
# which can create deadlocks (see 1470013) and a huge value which can cause
# MAAS to hit other limitations such as the number of open files or the
# number of concurrent database connexions.
MAX_THREADS = 100


@implementer(IServiceMaker, IPlugin)
class RegionServiceMaker:
    """Create a service for the Twisted plugin."""

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def _configureLogging(self):
        # Get something going with the logs.
        from provisioningserver import logger
        logger.basicConfig()

    def _configureDjango(self):
        # Some region services use the ORM at class-load time: force Django to
        # load the models first.
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

    def _configureCrochet(self):
        # Prevent other libraries from starting the reactor via crochet.
        # In other words, this makes crochet.setup() a no-op.
        import crochet
        crochet.no_setup()

    def _configurePoolSize(self):
        threadpool = reactor.getThreadPool()
        threadpool.adjustPoolsize(10, MAX_THREADS)

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

        self._configureLogging()
        self._configureDjango()
        self._checkDatabase()
        self._configureCrochet()
        self._configurePoolSize()

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
