# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event-loop support for the MAAS Region Controller.

This helps start up a background event loop (using Twisted, via crochet)
to handle communications with Cluster Controllers, and any other tasks
that are not tied to an HTTP reqoest.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "loop",
    "services",
    "start",
    "stop",
]

from functools import wraps
from logging import getLogger
from os import getpid
from socket import gethostname

import crochet
from django.utils import autoreload
from twisted.application.service import MultiService
from twisted.internet.error import ReactorNotRunning


logger = getLogger(__name__)


def stop_event_loop_when_reloader_is_invoked():
    """Stop the event loop if Django starts reloading itself.

    This typically only happens when using Django's development server.
    """
    # The original restart_with_reloader.
    restart_with_reloader = autoreload.restart_with_reloader

    @wraps(restart_with_reloader)
    def stop_event_loop_then_restart_with_reloader():
        logger.info("Stopping event loop in process %d", getpid())
        try:
            crochet.reactor.stop()
        except ReactorNotRunning:
            pass
        return restart_with_reloader()

    autoreload.restart_with_reloader = (
        stop_event_loop_then_restart_with_reloader)

stop_event_loop_when_reloader_is_invoked()


def make_RegionService():
    # Import here to avoid a circular import.
    from maasserver.rpc import regionservice
    return regionservice.RegionService()


def make_RegionAdvertisingService():
    # Import here to avoid a circular import.
    from maasserver.rpc import regionservice
    return regionservice.RegionAdvertisingService()


class RegionEventLoop:
    """An event loop running in a region controller process.

    Typically several processes will be running the web application -
    chiefly Django - across several machines, with multiple threads of
    execution in each process.

    This class represents a single event loop for each *process*,
    allowing convenient control of the event loop - a Twisted reactor
    running in a thread - and to which to attach and query services.
    """

    factories = (
        ("rpc", make_RegionService),
        ("rpc-advertise", make_RegionAdvertisingService),
    )

    def __init__(self):
        super(RegionEventLoop, self).__init__()
        self.services = MultiService()
        self.handle = None

    def init(self):
        """Spin up a Twisted event loop in this process."""
        if not crochet.reactor.running:
            logger.info("Starting event loop in process %d", getpid())
            crochet.setup()

    @crochet.run_in_reactor
    def start(self):
        for name, factory in self.factories:
            try:
                self.services.getServiceNamed(name)
            except KeyError:
                service = factory()
                service.setName(name)
                service.setServiceParent(self.services)
        self.handle = crochet.reactor.addSystemEventTrigger(
            'before', 'shutdown', self.services.stopService)
        return self.services.startService()

    @crochet.run_in_reactor
    def stop(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            crochet.reactor.removeSystemEventTrigger(handle)
        return self.services.stopService()

    @property
    def name(self):
        """A name for identifying this service in a distributed system."""
        return "%s:pid=%d" % (gethostname(), getpid())


loop = RegionEventLoop()
services = loop.services
start = loop.start
stop = loop.stop

loop.init()
