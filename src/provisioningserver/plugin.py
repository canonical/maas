# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS provisioning server"""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from getpass import getuser

from amqpclient import AMQFactory
from formencode import Schema
from formencode.validators import (
    Int,
    RequireIfPresent,
    String,
    URL,
    )
from provisioningserver.cobblerclient import CobblerSession
from provisioningserver.remote import ProvisioningAPI_XMLRPC
from provisioningserver.services import (
    LogService,
    OOPSService,
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
    username = String(if_missing=getuser())
    password = String(if_missing=b"test")
    vhost = String(if_missing="/")


class ConfigCobbler(Schema):
    """Configuration validator for connecting to Cobbler."""

    if_key_missing = None

    url = URL(
        add_http=True, require_tld=False,
        if_missing=b"http://localhost/cobbler_api",
        )
    username = String(if_missing=getuser())
    password = String(if_missing=b"test")


class Config(Schema):
    """Configuration validator."""

    if_key_missing = None

    interface = String(if_empty=b"", if_missing=b"127.0.0.1")
    port = Int(min=1, max=65535, if_missing=5241)
    logfile = String(if_empty=b"pserv.log", if_missing=b"pserv.log")
    oops = ConfigOops
    broker = ConfigBroker
    cobbler = ConfigCobbler

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

    def _makeLogService(self, config):
        """Create the log service."""
        return LogService(config["logfile"])

    def _makeOopsService(self, log_service, oops_config):
        """Create the oops service."""
        oops_dir = oops_config["directory"]
        oops_reporter = oops_config["reporter"]
        return OOPSService(log_service, oops_dir, oops_reporter)

    def _makePAPI(self, cobbler_config):
        """Create the provisioning XMLRPC API."""
        cobbler_session = CobblerSession(
            cobbler_config["url"], cobbler_config["username"],
            cobbler_config["password"])
        return ProvisioningAPI_XMLRPC(cobbler_session)

    def _makeSiteService(self, papi_xmlrpc, config):
        """Create the site service."""
        site_root = Resource()
        site_root.putChild("api", papi_xmlrpc)
        site = Site(site_root)
        site_port = config["port"]
        site_interface = config["interface"]
        site_service = TCPServer(site_port, site, interface=site_interface)
        site_service.setName("site")
        return site_service

    def _makeBroker(self, broker_config):
        """Create the messaging broker."""
        broker_port = broker_config["port"]
        broker_host = broker_config["host"]
        broker_username = broker_config["username"]
        broker_password = broker_config["password"]
        broker_vhost = broker_config["vhost"]

        cb_connected = lambda ignored: None  # TODO
        cb_disconnected = lambda ignored: None  # TODO
        cb_failed = lambda connector_and_reason: (
            log.err(connector_and_reason[1], "Connection failed"))
        client_factory = AMQFactory(
            broker_username, broker_password, broker_vhost,
            cb_connected, cb_disconnected, cb_failed)
        client_service = TCPClient(
            broker_host, broker_port, client_factory)
        client_service.setName("amqp")
        return client_service

    def makeService(self, options):
        """Construct a service."""
        services = MultiService()
        config = Config.load(options["config-file"])

        log_service = self._makeLogService(config)
        log_service.setServiceParent(services)

        oops_service = self._makeOopsService(log_service, config["oops"])
        oops_service.setServiceParent(services)

        broker_config = config["broker"]
        # Connecting to RabbitMQ is not yet a required component of a running
        # MAAS installation; skip unless the password has been set explicitly.
        if broker_config["password"] is not b"test":
            client_service = self._makeBroker(broker_config)
            client_service.setServiceParent(services)

        papi_xmlrpc = self._makePAPI(config["cobbler"])
        site_service = self._makeSiteService(papi_xmlrpc, config)
        site_service.setServiceParent(services)

        return services
