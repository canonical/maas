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
from formencode import Schema
from formencode.validators import (
    Int,
    RequireIfPresent,
    String,
    )
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
import yaml
from zope.interface import implements


class ConfigOops(Schema):
    """Configuration validator for OOPS options."""

    if_key_missing = None

    directory = String(if_missing=b"")
    reporter = String(if_missing=b"")

    chained_validators = (
        RequireIfPresent("reporter", present="directory"),
        )


class ConfigBroker(Schema):
    """Configuration validator for message broker options."""

    if_key_missing = None

    host = String(if_missing=b"localhost")
    port = Int(min=1, max=65535, if_missing=5673)
    username = String(if_missing=None)
    password = String(if_missing=None)
    vhost = String(if_missing="/")


class Config(Schema):
    """Configuration validator."""

    if_key_missing = None

    port = Int(min=1, max=65535, if_missing=8001)
    logfile = String(not_empty=True)
    oops = ConfigOops
    broker = ConfigBroker

    @classmethod
    def parse(cls, stream):
        """Load a YAML configuration from `stream` and validate."""
        return cls().to_python(yaml.load(stream))

    @classmethod
    def load(cls, filename):
        """Load a YAML configuration from `filename` and validate."""
        with open(filename, "rb") as stream:
            return cls.parse(stream)


class Options(usage.Options):
    """Command line options for the provisioning server."""

    optParameters = [
        ["config-file", "c", "pserv.yaml", "Configuration file to load."],
        ]


class ProvisioningServiceMaker(object):
    """Create a service for the Twisted plugin."""

    implements(IServiceMaker, IPlugin)

    options = Options

    def __init__(self, name, description):
        self.tapname = name
        self.description = description

    def makeService(self, options):
        """Construct a service."""
        services = MultiService()

        config_file = options["config-file"]
        if config_file is None:
            config = Config.parse(b"")
        else:
            config = Config.load(config_file)

        log_service = LogService(config["logfile"])
        log_service.setServiceParent(services)

        oops_config = config["oops"]
        oops_dir = oops_config["directory"]
        oops_reporter = oops_config["reporter"]
        oops_service = OOPSService(log_service, oops_dir, oops_reporter)
        oops_service.setServiceParent(services)

        broker_config = config["broker"]
        broker_port = broker_config["port"]
        broker_host = broker_config["host"]
        broker_username = broker_config["username"]
        broker_password = broker_config["password"]
        broker_vhost = broker_config["vhost"]

        # Connecting to RabbitMQ is optional; it is not yet a required
        # component of a running MaaS installation.
        if broker_username is not None and broker_password is not None:
            cb_connected = lambda ignored: None  # TODO
            cb_disconnected = lambda ignored: None  # TODO
            cb_failed = lambda (connector, reason): (
                log.err(reason, "Connection failed"))
            client_factory = AMQFactory(
                broker_username, broker_password, broker_vhost,
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
        site_port = config["port"]
        site_service = TCPServer(site_port, site)
        site_service.setName("site")
        site_service.setServiceParent(services)

        return services
