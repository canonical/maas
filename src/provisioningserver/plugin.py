# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MaaS provisioning server"""

from __future__ import (
    print_function,
    unicode_literals,
    )

import setproctitle
import signal
import sys

import oops
from oops_datedir_repo import DateDirRepo
from oops_twisted import (
    Config as oops_config,
    defer_publisher,
    OOPSObserver,
    )
from twisted.application.internet import TCPClient
from twisted.application.service import (
    IServiceMaker,
    MultiService,
    )
from twisted.internet import reactor
from twisted.plugin import IPlugin
from twisted.python import (
    log,
    usage,
    )
from twisted.python.logfile import LogFile
from twisted.python.log import (
    addObserver,
    FileLogObserver,
    )
from zope.interface import implements

from amqpclient import AMQFactory

__metaclass__ = type
__all__ = []


def getRotatableLogFileObserver(filename):
    """Setup a L{LogFile} for the given application."""
    if filename != '-':
        logfile = LogFile.fromFullPath(
            filename, rotateLength=None, defaultMode=0644)
        def signal_handler(sig, frame):
            reactor.callFromThread(logfile.reopen)
        signal.signal(signal.SIGUSR1, signal_handler)
    else:
        logfile = sys.stdout
    return FileLogObserver(logfile)


def setUpOOPSHandler(options, logfile):
    """Add OOPS handling based on the passed command line options."""
    config = oops_config()

    # Add the oops publisher that writes files in the configured place
    # if the command line option was set.

    if options["oops-dir"]:
        repo = DateDirRepo(options["oops-dir"])
        config.publishers.append(
            defer_publisher(oops.publish_new_only(repo.publish)))

    if options["oops-reporter"]:
        config.template['reporter'] = options["oops-reporter"]

    observer = OOPSObserver(config, logfile.emit)
    addObserver(observer.emit)
    return observer


class Options(usage.Options):
    """Command line options for the provisioning server."""

    optParameters = [
        ["logfile", "l", "provisioningserver.log", "Logfile name."],
        ["brokerport", "p", 5672, "Broker port"],
        ["brokerhost", "h", '127.0.0.1', "Broker host"],
        ["brokeruser", "u", None, "Broker user"],
        ["brokerpassword", "a", None, "Broker password"],
        ["brokervhost", "v", '/', "Broker vhost"],
        ["oops-dir", "r", None, "Where to write OOPS reports"],
        ["oops-reporter", "o", "MAAS-PS", "String identifying this service."],
        ]

    def postOptions(self):
        for arg in ('brokeruser', 'brokerpassword'):
            if not self[arg]:
                raise usage.UsageError("--%s must be specified." % arg)
        for int_arg in ('brokerport',):
            try:
                self[int_arg] = int(self[int_arg])
            except (TypeError, ValueError):
                raise usage.UsageError("--%s must be an integer." % int_arg)
        if not self["oops-reporter"] and self["oops-dir"]:
            raise usage.UsageError(
                "A reporter must be supplied to identify reports "
                "from this service from other OOPS reports.")

class ProvisioningServiceMaker(object):
    """Create a service for the Twisted plugin."""

    implements(IServiceMaker, IPlugin)

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def makeService(self, options):
        """Construct a service."""
        # Required to hide the command line options that include a password.
        # There is a small window where it can be seen though, between
        # invocation and when this code runs.
        setproctitle.setproctitle("maas provisioning service")

        logfile = getRotatableLogFileObserver(options["logfile"])
        setUpOOPSHandler(options, logfile)

        broker_port = options["brokerport"]
        broker_host = options["brokerhost"]
        broker_user = options["brokeruser"]
        broker_password = options["brokerpassword"]
        broker_vhost = options["brokervhost"]

        # TODO: define callbacks for Rabbit connectivity.
        # e.g. construct a manager object.
        client_factory = AMQFactory(
            broker_user, broker_password, broker_vhost,
            CONNECTED_CALLBACK, DISCONNECTED_CALLBACK,
            lambda (connector, reason): log.err(reason, "Connection failed"))

        # TODO: Create services here, e.g.
        # service1 = thing
        # service2 = thing2
        # services = MultiService()
        # services.addService(service1)
        # services.addService(service2)
        # return services

        client_service = TCPClient(broker_host, broker_port, client_factory)
        services = MultiService()
        services.addService(client_service)
        return services
