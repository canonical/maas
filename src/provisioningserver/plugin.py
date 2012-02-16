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
from provisioningserver.cobblerclient import CobblerSession
from provisioningserver.remote import ProvisioningAPI_XMLRPC
from provisioningserver.services import (
    LogService,
    OOPSService,
    )
from provisioningserver.testing.fakecobbler import (
    FakeCobbler,
    FakeTwistedProxy,
    )
import setproctitle
from twisted.application.internet import (
    TCPClient,
    TCPServer,
    )
from twisted.application.service import (
    IServiceMaker,
    MultiService,
    )
from twisted.plugin import IPlugin
from twisted.python import (
    log,
    usage,
    )
from twisted.web.resource import Resource
from twisted.web.server import Site
from zope.interface import implements


class Options(usage.Options):
    """Command line options for the provisioning server."""

    optParameters = [
        ["port", None, 8001, "Port to serve on."],
        ["logfile", "l", "pserv.log", "Logfile name."],
        ["oops-dir", "r", None, "Where to write OOPS reports"],
        ["oops-reporter", "o", "MAAS-PS", "String identifying this service."],
        ]

    # Move these back into optParameters when RabbitMQ is a required component
    # of a running MaaS installation.
    optParameters_FOR_RABBIT = [
        ["brokerport", "p", 5672, "Broker port"],
        ["brokerhost", "h", '127.0.0.1', "Broker host"],
        ["brokeruser", "u", None, "Broker user"],
        ["brokerpassword", "a", None, "Broker password"],
        ["brokervhost", "v", '/', "Broker vhost"],
        ]

    def postOptions(self):
        for int_arg in ('port',):
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

        log_service = LogService(options["logfile"])
        log_service.setServiceParent(services)

        oops_dir = options["oops-dir"]
        oops_reporter = options["oops-reporter"]
        oops_service = OOPSService(log_service, oops_dir, oops_reporter)
        oops_service.setServiceParent(services)

        broker_port = options.get("brokerport")
        broker_host = options.get("brokerhost")
        broker_user = options.get("brokeruser")
        broker_password = options.get("brokerpassword")
        broker_vhost = options.get("brokervhost")

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

        session = CobblerSession(
            # TODO: Get these values from command-line arguments.
            "http://localhost/does/not/exist", "user", "password")

        # TODO: Remove this.
        fake_cobbler = FakeCobbler({"user": "password"})
        fake_cobbler_proxy = FakeTwistedProxy(fake_cobbler)
        session.proxy = fake_cobbler_proxy

        site_root = Resource()
        site_root.putChild("api", ProvisioningAPI_XMLRPC(session))
        site = Site(site_root)
        site_port = options["port"]
        site_service = TCPServer(site_port, site)
        site_service.setName("site")
        site_service.setServiceParent(services)

        return services
