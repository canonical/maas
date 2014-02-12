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
    "services",
    "start",
    "stop",
]

from functools import wraps
from logging import getLogger
from os import getpid

import crochet
from django.utils import autoreload
from maasserver.rpc.regionservice import RegionService
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


class RegionEventLoop:

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
        try:
            rpc = self.services.getServiceNamed("rpc")
        except KeyError:
            rpc = RegionService(crochet.reactor)
            rpc.setName("rpc")
            rpc.setServiceParent(self.services)

        self.handle = crochet.reactor.addSystemEventTrigger(
            'before', 'shutdown', self.services.stopService)
        return self.services.startService()

    @crochet.run_in_reactor
    def stop(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            crochet.reactor.removeSystemEventTrigger(handle)
        return self.services.stopService()


loop = RegionEventLoop()
services = loop.services
start = loop.start
stop = loop.stop
init = loop.init

init()
