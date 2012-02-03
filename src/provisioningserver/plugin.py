# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MaaS provisioning server"""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from amqpclient import AMQFactory
from provisioningserver.services import (
    LogService,
    OOPSService,
    )
import setproctitle
from twisted.application.internet import TCPClient
from twisted.application.service import (
    IServiceMaker,
    MultiService,
    )
from twisted.plugin import IPlugin
from twisted.python import (
    log,
    usage,
    )
from zope.interface import implements


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

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def makeService(self, options, _set_proc_title=True):
        """Construct a service.

        :param _set_proc_title: For testing; if `False` this will stop the
            obfuscation of command-line parameters in the process title.
        """
        # Required to hide the command line options that include a password.
        # There is a small window where it can be seen though, between
        # invocation and when this code runs. TODO: Make this optional (so
        # that we don't override process title in tests).
        if _set_proc_title:
            setproctitle.setproctitle("maas provisioning service")

        services = MultiService()

        logging_service = LogService(options["logfile"])
        logging_service.setServiceParent(services)

        oops_service = OOPSService(
            logging_service, options["oops-dir"], options["oops-reporter"])
        oops_service.setServiceParent(services)

        broker_port = options["brokerport"]
        broker_host = options["brokerhost"]
        broker_user = options["brokeruser"]
        broker_password = options["brokerpassword"]
        broker_vhost = options["brokervhost"]

        # Connecting to RabbitMQ is optional; it is not yet a required
        # component of a running MaaS installation.
        if broker_user is not None and broker_password is not None:
            cb_connected = lambda ignored: None  # TODO
            cb_disconnected = lambda ignored: None  # TODO
            cb_failed = lambda (connector, reason): (
                log.err(reason, "Connection failed"))
            client_factory = AMQFactory(
                broker_user, broker_password, broker_vhost,
                cb_connected, cb_disconnected, cb_failed)
            client_service = TCPClient(
                broker_host, broker_port, client_factory)
            client_service.setName("amqp")
            client_service.setServiceParent(services)

        return services
