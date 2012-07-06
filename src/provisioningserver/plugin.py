# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS provisioning server"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from getpass import getuser
from os import getcwd

from formencode import Schema
from formencode.validators import (
    Int,
    RequireIfPresent,
    String,
    URL,
    )
from provisioningserver.amqpclient import AMQFactory
from provisioningserver.cobblerclient import CobblerSession
from provisioningserver.remote import ProvisioningAPI_XMLRPC
from provisioningserver.services import (
    LogService,
    OOPSService,
    )
from provisioningserver.tftp import TFTPBackend
from tftp.protocol import TFTP
from twisted.application import internet
from twisted.application.internet import (
    TCPClient,
    TCPServer,
    )
from twisted.application.service import (
    IServiceMaker,
    MultiService,
    )
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import (
    IRealm,
    Portal,
    )
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.plugin import IPlugin
from twisted.python import (
    log,
    usage,
    )
from twisted.web.guard import (
    BasicCredentialFactory,
    HTTPAuthSessionWrapper,
    )
from twisted.web.resource import (
    IResource,
    Resource,
    )
from twisted.web.server import Site
import yaml
from zope.interface import implementer


@implementer(ICredentialsChecker)
class SingleUsernamePasswordChecker:
    """An `ICredentialsChecker` for a single username and password."""

    credentialInterfaces = [IUsernamePassword]

    def __init__(self, username, password):
        super(SingleUsernamePasswordChecker, self).__init__()
        self.username = username
        self.password = password

    @inlineCallbacks
    def requestAvatarId(self, credentials):
        """See `ICredentialsChecker`."""
        if credentials.username == self.username:
            matched = yield credentials.checkPassword(self.password)
            if matched:
                returnValue(credentials.username)
        raise UnauthorizedLogin(credentials.username)


@implementer(IRealm)
class ProvisioningRealm:
    """The `IRealm` for the Provisioning API."""

    noop = staticmethod(lambda: None)

    def __init__(self, resource):
        super(ProvisioningRealm, self).__init__()
        self.resource = resource

    def requestAvatar(self, avatarId, mind, *interfaces):
        """See `IRealm`."""
        if IResource in interfaces:
            return (IResource, self.resource, self.noop)
        raise NotImplementedError()


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


class ConfigTFTP(Schema):
    """Configuration validator for the TFTP service."""

    if_key_missing = None

    root = String(if_missing=getcwd())
    port = Int(min=1, max=65535, if_missing=5244)
    generator = URL(
        add_http=True, require_tld=False,
        if_missing=b"http://localhost:5243/api/1.0/pxeconfig",
        )


class Config(Schema):
    """Configuration validator."""

    if_key_missing = None

    interface = String(if_empty=b"", if_missing=b"127.0.0.1")
    port = Int(min=1, max=65535, if_missing=5241)
    username = String(not_empty=True, if_missing=getuser())
    password = String(not_empty=True)
    logfile = String(if_empty=b"pserv.log", if_missing=b"pserv.log")
    oops = ConfigOops
    broker = ConfigBroker
    cobbler = ConfigCobbler
    tftp = ConfigTFTP

    @classmethod
    def parse(cls, stream):
        """Load a YAML configuration from `stream` and validate."""
        return cls.to_python(yaml.safe_load(stream))

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


@implementer(IServiceMaker, IPlugin)
class ProvisioningServiceMaker(object):
    """Create a service for the Twisted plugin."""

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

    def _makeCobblerSession(self, cobbler_config):
        """Create a :class:`CobblerSession`."""
        return CobblerSession(
            cobbler_config["url"], cobbler_config["username"],
            cobbler_config["password"])

    def _makeProvisioningAPI(self, cobbler_session, config):
        """Construct an :class:`IResource` for the Provisioning API."""
        papi_xmlrpc = ProvisioningAPI_XMLRPC(cobbler_session)
        papi_realm = ProvisioningRealm(papi_xmlrpc)
        papi_checker = SingleUsernamePasswordChecker(
            config["username"], config["password"])
        papi_portal = Portal(papi_realm, [papi_checker])
        papi_creds = BasicCredentialFactory(b"MAAS Provisioning API")
        papi_root = HTTPAuthSessionWrapper(papi_portal, [papi_creds])
        return papi_root

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

    def _makeTFTPService(self, tftp_config):
        """Create the dynamic TFTP service."""
        backend = TFTPBackend(tftp_config["root"], tftp_config["generator"])
        factory = TFTP(backend)
        tftp_service = internet.UDPServer(tftp_config["port"], factory)
        tftp_service.setName("tftp")
        return tftp_service

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
        if broker_config["password"] != b"test":
            client_service = self._makeBroker(broker_config)
            client_service.setServiceParent(services)

        cobbler_config = config["cobbler"]
        cobbler_session = self._makeCobblerSession(cobbler_config)

        papi_root = self._makeProvisioningAPI(cobbler_session, config)

        site_service = self._makeSiteService(papi_root, config)
        site_service.setServiceParent(services)

        tftp_service = self._makeTFTPService(config["tftp"])
        tftp_service.setServiceParent(services)

        return services
