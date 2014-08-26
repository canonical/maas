# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin code for the MAAS provisioning server"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "LogService",
    "OOPSService",
    "ProvisioningServiceMaker",
]

import signal
import sys

import oops
from oops_datedir_repo import DateDirRepo
from oops_twisted import (
    Config as oops_config,
    defer_publisher,
    OOPSObserver,
    )
import provisioningserver
from provisioningserver.cluster_config import get_cluster_uuid
from provisioningserver.config import Config
from provisioningserver.dhcp.dhcp_probe_service import (
    PeriodicDHCPProbeService,
    )
from provisioningserver.rpc.boot_images import PeriodicImageDownloadService
from provisioningserver.rpc.clusterservice import ClusterClientService
from provisioningserver.rpc.power import NodePowerMonitorService
from provisioningserver.tftp import TFTPService
from twisted.application.internet import TCPServer
from twisted.application.service import (
    IServiceMaker,
    Service,
    )
from twisted.cred.checkers import ICredentialsChecker
from twisted.cred.credentials import IUsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm
from twisted.internet import reactor
from twisted.internet.defer import (
    inlineCallbacks,
    returnValue,
    )
from twisted.plugin import IPlugin
from twisted.python import usage
from twisted.python.log import (
    addObserver,
    FileLogObserver,
    removeObserver,
    )
from twisted.python.logfile import LogFile
from twisted.web.resource import (
    IResource,
    Resource,
    )
from twisted.web.server import Site
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


class LogService(Service):

    name = "log"

    def __init__(self, filename):
        self.filename = filename
        self.logfile = None
        self.observer = None

    def _signal_handler(self, sig, frame):
        reactor.callFromThread(self.logfile.reopen)

    def startService(self):
        Service.startService(self)
        if self.filename != '-':
            self.logfile = LogFile.fromFullPath(
                self.filename, rotateLength=None, defaultMode=0o644)
            self.__previous_signal_handler = signal.signal(
                signal.SIGUSR1, self._signal_handler)
        else:
            self.logfile = sys.stdout
        self.observer = FileLogObserver(self.logfile)
        self.observer.start()

    def stopService(self):
        Service.stopService(self)
        if self.filename != '-':
            signal.signal(signal.SIGUSR1, self.__previous_signal_handler)
            del self.__previous_signal_handler
            self.observer.stop()
            self.observer = None
            self.logfile.close()
            self.logfile = None
        else:
            self.observer.stop()
            self.observer = None
            # Don't close stdout.
            self.logfile = None


class OOPSService(Service):

    name = "oops"

    def __init__(self, log_service, oops_dir, oops_reporter):
        self.config = None
        self.log_service = log_service
        self.oops_dir = oops_dir
        self.oops_reporter = oops_reporter

    def startService(self):
        Service.startService(self)
        self.config = oops_config()
        # Add the oops publisher that writes files in the configured place if
        # the command line option was set.
        if self.oops_dir:
            repo = DateDirRepo(self.oops_dir)
            self.config.publishers.append(
                defer_publisher(oops.publish_new_only(repo.publish)))
        if self.oops_reporter:
            self.config.template['reporter'] = self.oops_reporter
        self.observer = OOPSObserver(
            self.config, self.log_service.observer.emit)
        addObserver(self.observer.emit)

    def stopService(self):
        Service.stopService(self)
        removeObserver(self.observer.emit)
        self.observer = None
        self.config = None


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

    def _makeTFTPService(self, tftp_config):
        """Create the dynamic TFTP service."""
        tftp_service = TFTPService(
            resource_root=tftp_config['resource_root'],
            port=tftp_config['port'], generator=tftp_config['generator'])
        tftp_service.setName("tftp")
        return tftp_service

    def _makePeriodicImageDownloadService(self, rpc_service):
        image_download_service = PeriodicImageDownloadService(
            rpc_service, reactor, get_cluster_uuid())
        image_download_service.setName("image_download")
        return image_download_service

    def _makeNodePowerMonitorService(self, rpc_service):
        node_monitor = NodePowerMonitorService(
            rpc_service, reactor, get_cluster_uuid())
        node_monitor.setName("node_monitor")
        return node_monitor

    def _makeRPCService(self, rpc_config):
        rpc_service = ClusterClientService(reactor)
        rpc_service.setName("rpc")
        return rpc_service

    def _makePeriodicDHCPProbeService(self, rpc_service):
        dhcp_probe_service = PeriodicDHCPProbeService(
            reactor, get_cluster_uuid())
        dhcp_probe_service.setName("dhcp_probe")
        return dhcp_probe_service

    def makeService(self, options):
        """Construct a service."""
        services = provisioningserver.services
        config = Config.load(options["config-file"])

        log_service = self._makeLogService(config)
        log_service.setServiceParent(services)

        oops_service = self._makeOopsService(log_service, config["oops"])
        oops_service.setServiceParent(services)

        tftp_service = self._makeTFTPService(config["tftp"])
        tftp_service.setServiceParent(services)

        rpc_service = self._makeRPCService(config["rpc"])
        rpc_service.setServiceParent(services)

        node_monitor = self._makeNodePowerMonitorService(rpc_service)
        node_monitor.setServiceParent(services)

        image_download_service = self._makePeriodicImageDownloadService(
            rpc_service)
        image_download_service.setServiceParent(services)

        dhcp_probe_service = self._makePeriodicDHCPProbeService(rpc_service)
        dhcp_probe_service.setServiceParent(services)

        return services
