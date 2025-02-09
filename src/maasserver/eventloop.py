# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Event-loop support for the MAAS Region Controller.

This helps start up a background event loop (using Twisted, via crochet)
to handle communications with Cluster Controllers, and any other tasks
that are not tied to an HTTP request.

.. py:data:: loop

   The single instance of :py:class:`RegionEventLoop` that's all a
   process needs.

.. py:data:: services

   The :py:class:`~twisted.application.service.MultiService` which forms
   the root of this process's service tree.

   This is a convenient reference to :py:attr:`.loop.services`.

.. py:data:: start

   Start all the services in :py:data:`services`.

   This is a convenient reference to :py:attr:`.loop.start`.

.. py:data:: stop

   Stop all the services in :py:data:`services`.

   This is a convenient reference to :py:attr:`.loop.stop`.

.. py:data:: restart

   Restart all the services in :py:data:`services`.

   This is a convenient reference to :py:attr:`.loop.restart`.

"""

import logging
import os
from socket import gethostname

from twisted.application.service import MultiService, Service
from twisted.internet import reactor
from twisted.internet.defer import DeferredList, inlineCallbacks, maybeDeferred

from maasserver.utils.orm import disable_all_database_connections
from provisioningserver.prometheus.metrics import set_global_labels
from provisioningserver.utils.env import MAAS_UUID
from provisioningserver.utils.twisted import asynchronous, call

# Default port for regiond.
DEFAULT_PORT = 5240

reactor.addSystemEventTrigger(
    "before", "startup", disable_all_database_connections
)

logger = logging.getLogger(f"{__name__}_{os.getpid()}")


def make_DatabaseTaskService():
    from maasserver.utils import dbtasks

    return dbtasks.DatabaseTasksService()


def make_RegionControllerService(postgresListener, dbtasks):
    from maasserver.region_controller import RegionControllerService

    return RegionControllerService(postgresListener, dbtasks)


def make_RegionService(ipcWorker):
    # Import here to avoid a circular import.
    from maasserver.rpc import regionservice

    return regionservice.RegionService(ipcWorker)


def make_NonceCleanupService():
    from maasserver import nonces_cleanup

    return nonces_cleanup.NonceCleanupService()


def make_DNSPublicationGarbageService():
    from maasserver.dns import publication

    return publication.DNSPublicationGarbageService()


def make_StatusMonitorService():
    from maasserver import status_monitor

    return status_monitor.StatusMonitorService()


def make_StatsService():
    from maasserver import stats

    return stats.StatsService()


def make_PrometheusService():
    from maasserver.prometheus import stats

    return stats.PrometheusService()


def make_ImportResourcesService():
    from maasserver import bootresources

    return bootresources.ImportResourcesService()


def make_ImportResourcesProgressService():
    from maasserver import bootresources

    return bootresources.ImportResourcesProgressService()


def make_PostgresListenerService():
    from maasserver.listener import PostgresListenerService

    return PostgresListenerService()


def make_RackControllerService(ipcWorker, postgresListener):
    from maasserver.rack_controller import RackControllerService

    return RackControllerService(ipcWorker, postgresListener)


def make_StatusWorkerService(dbtasks):
    from metadataserver.api_twisted import StatusWorkerService

    return StatusWorkerService(dbtasks)


def make_ServiceMonitorService():
    from maasserver.regiondservices import service_monitor_service

    return service_monitor_service.ServiceMonitorService()


def make_NetworksMonitoringService():
    from maasserver.regiondservices.networks_monitoring import (
        RegionNetworksMonitoringService,
    )

    return RegionNetworksMonitoringService(reactor)


def make_ActiveDiscoveryService(postgresListener):
    from maasserver.regiondservices.active_discovery import (
        ActiveDiscoveryService,
    )

    return ActiveDiscoveryService(reactor, postgresListener)


def make_ReverseDNSService(postgresListener):
    from maasserver.regiondservices.reverse_dns import ReverseDNSService

    return ReverseDNSService(postgresListener)


def make_NetworkTimeProtocolService():
    from maasserver.regiondservices import ntp

    return ntp.RegionNetworkTimeProtocolService(reactor)


def make_SyslogService():
    from maasserver.regiondservices import syslog

    return syslog.RegionSyslogService(reactor)


def make_HTTPService(postgresListener):
    from maasserver.regiondservices import http

    return http.RegionHTTPService(postgresListener)


def make_TemporalService():
    from maasserver.regiondservices import temporal

    return temporal.RegionTemporalService()


def make_TemporalWorker():
    from maasserver.regiondservices import temporal_worker

    return temporal_worker.TemporalWorkerService(reactor)


def make_WebApplicationService(postgresListener, statusWorker):
    from maasserver.webapp import WebApplicationService

    site_service = WebApplicationService(postgresListener, statusWorker)
    return site_service


def make_VersionUpdateCheckService():
    from maasserver.regiondservices.version_update_check import (
        RegionVersionUpdateCheckService,
    )

    return RegionVersionUpdateCheckService(reactor)


def make_WorkersService():
    from maasserver.workers import WorkersService

    return WorkersService(reactor)


def make_IPCMasterService(workers=None):
    from maasserver.ipc import IPCMasterService

    return IPCMasterService(reactor, workers)


def make_IPCWorkerService():
    from maasserver.ipc import IPCWorkerService

    return IPCWorkerService(reactor)


def make_PrometheusExporterService():
    from maasserver.prometheus.service import (
        create_prometheus_exporter_service,
        REGION_PROMETHEUS_PORT,
    )

    return create_prometheus_exporter_service(reactor, REGION_PROMETHEUS_PORT)


def make_CertificateExpirationCheckService():
    from maasserver.regiondservices.certificate_expiration_check import (
        CertificateExpirationCheckService,
    )

    return CertificateExpirationCheckService(reactor)


def make_VaultSecretsCleanupService():
    from maasserver.regiondservices.vault_secrets_cleanup import (
        VaultSecretsCleanupService,
    )

    return VaultSecretsCleanupService(reactor)


class MAASServices(MultiService):
    def __init__(self, eventloop):
        self.eventloop = eventloop
        super().__init__()

    @asynchronous
    @inlineCallbacks
    def startService(self):
        yield maybeDeferred(self.eventloop.prepare)
        Service.startService(self)
        self._set_globals()
        yield DeferredList(
            [maybeDeferred(service.startService) for service in self]
        )

    def _set_globals(self):
        set_global_labels(maas_uuid=MAAS_UUID.get())


class RegionEventLoop:
    """An event loop running in a region controller process.

    Typically several processes will be running the web application --
    chiefly Django -- across several machines, with multiple threads of
    execution in each processingle event loop for each *process*,
    allowing convenient control of the event loop -- a Twisted reactor
    running in a thread -- and to which to attach and query services.

    :cvar factories: A sequence of ``(name, factory)`` tuples. Used to
        populate :py:attr:`.services` at start time.

    :ivar services:
        A :py:class:`~twisted.application.service.MultiService` which
        forms the root of the service tree.

    """

    factories = {
        "database-tasks": {
            "only_on_master": False,
            "factory": make_DatabaseTaskService,
            "requires": [],
        },
        "database-tasks-master": {
            "only_on_master": True,
            "factory": make_DatabaseTaskService,
            "requires": [],
        },
        "region-controller": {
            "only_on_master": True,
            "factory": make_RegionControllerService,
            "requires": ["postgres-listener-master", "database-tasks-master"],
        },
        "rpc": {
            "only_on_master": False,
            "factory": make_RegionService,
            "requires": ["ipc-worker"],
        },
        "nonce-cleanup": {
            "only_on_master": True,
            "factory": make_NonceCleanupService,
            "requires": [],
        },
        "dns-publication-cleanup": {
            "only_on_master": True,
            "factory": make_DNSPublicationGarbageService,
            "requires": [],
        },
        "status-monitor": {
            "only_on_master": True,
            "factory": make_StatusMonitorService,
            "requires": [],
        },
        "stats": {
            "only_on_master": True,
            "factory": make_StatsService,
            "requires": [],
        },
        "prometheus": {
            "only_on_master": True,
            "factory": make_PrometheusService,
            "requires": [],
        },
        "import-resources": {
            "only_on_master": False,
            "import_service": True,
            "factory": make_ImportResourcesService,
            "requires": [],
        },
        "import-resources-progress": {
            "only_on_master": False,
            "import_service": True,
            "factory": make_ImportResourcesProgressService,
            "requires": [],
        },
        "postgres-listener-master": {
            "only_on_master": True,
            "factory": make_PostgresListenerService,
            "requires": [],
        },
        "postgres-listener-worker": {
            "only_on_master": False,
            "factory": make_PostgresListenerService,
            "requires": [],
        },
        "web": {
            "only_on_master": False,
            "factory": make_WebApplicationService,
            "requires": ["postgres-listener-worker", "status-worker"],
        },
        "prometheus-exporter": {
            "only_on_master": True,
            "factory": make_PrometheusExporterService,
            "requires": [],
        },
        "service-monitor": {
            "only_on_master": True,
            "factory": make_ServiceMonitorService,
            "requires": [],
        },
        "status-worker": {
            "only_on_master": False,
            "factory": make_StatusWorkerService,
            "requires": ["database-tasks"],
        },
        "networks-monitor": {
            "only_on_master": True,
            "factory": make_NetworksMonitoringService,
            "requires": [],
        },
        "active-discovery": {
            "only_on_master": False,
            "import_service": True,  # run on worker #1
            "factory": make_ActiveDiscoveryService,
            "requires": ["postgres-listener-worker"],
        },
        "reverse-dns": {
            "only_on_master": True,
            "factory": make_ReverseDNSService,
            "requires": ["postgres-listener-master"],
        },
        "rack-controller": {
            "only_on_master": False,
            "factory": make_RackControllerService,
            "requires": ["ipc-worker", "postgres-listener-worker"],
        },
        "ntp": {
            "only_on_master": True,
            "factory": make_NetworkTimeProtocolService,
            "requires": [],
        },
        "syslog": {
            "only_on_master": True,
            "factory": make_SyslogService,
            "requires": [],
        },
        "version-check": {
            "only_on_master": True,
            "factory": make_VersionUpdateCheckService,
            "requires": [],
        },
        "workers": {
            "only_on_master": True,
            "not_all_in_one": True,
            "factory": make_WorkersService,
            "requires": [],
        },
        "ipc-master": {
            "only_on_master": True,
            "factory": make_IPCMasterService,
            "requires": [],
            "optional": ["workers"],
        },
        "ipc-worker": {
            "only_on_master": False,
            "factory": make_IPCWorkerService,
            "requires": [],
        },
        "reverse-proxy": {
            "only_on_master": True,
            "factory": make_HTTPService,
            "requires": ["postgres-listener-master"],
        },
        "certificate-expiration-check": {
            "only_on_master": True,
            "factory": make_CertificateExpirationCheckService,
            "requires": [],
        },
        "vault-secrets-cleanup": {
            "only_on_master": True,
            "factory": make_VaultSecretsCleanupService,
            "requires": [],
        },
        "temporal": {
            "only_on_master": True,
            "factory": make_TemporalService,
            "requires": [],
        },
        "temporal-worker": {
            "only_on_master": True,
            "factory": make_TemporalWorker,
            "requires": [],
        },
    }

    def __init__(self):
        super().__init__()
        self.services = MAASServices(self)
        self.handle = None
        self.master = False
        self.all_in_one = False
        self.logger = logger.getChild("generic")

    @asynchronous
    def populateService(
        self, name, master=False, all_in_one=False, import_services=False
    ):
        """Prepare a service."""
        factoryInfo = self.factories[name]
        if not all_in_one:
            if factoryInfo["only_on_master"] and not master:
                raise ValueError(
                    "Service '%s' cannot be created because it can only run "
                    "on the master process." % name
                )
            elif not factoryInfo["only_on_master"] and master:
                raise ValueError(
                    "Service '%s' cannot be created because it can only run "
                    "on a worker process." % name
                )
        else:
            dont_run = factoryInfo.get("not_all_in_one", False)
            if dont_run:
                raise ValueError(
                    "Service '%s' cannot be created because it can not run "
                    "in the all-in-one process." % name
                )
        if factoryInfo.get("import_service", False) and not import_services:
            raise ValueError(
                "Service '%s' cannot be created because import services "
                "should not run on this process." % name
            )
        try:
            service = self.services.getServiceNamed(name)
        except KeyError:
            # Get all dependent services for this services.
            dependencies = []
            optional_args = {}
            for require in factoryInfo["requires"]:
                dependencies.append(
                    self.populateService(
                        require,
                        master=master,
                        all_in_one=all_in_one,
                        import_services=import_services,
                    )
                )
            for optional in factoryInfo.get("optional", []):
                try:
                    service = self.populateService(
                        optional,
                        master=master,
                        all_in_one=all_in_one,
                        import_services=import_services,
                    )
                except ValueError:
                    pass
                else:
                    optional_args[optional] = service

            # Create the service with dependencies.
            service = factoryInfo["factory"](*dependencies, **optional_args)
            service.setName(name)
            service.setServiceParent(self.services)
        return service

    @asynchronous
    def populate(self, master=False, all_in_one=False, import_services=False):
        """Prepare services."""
        self.logger = logger.getChild("master" if master else "worker")
        self.master = master
        self.all_in_one = all_in_one
        for name, item in self.factories.items():
            if all_in_one:
                if not item.get("not_all_in_one", False):
                    self.populateService(
                        name,
                        master=master,
                        all_in_one=all_in_one,
                        import_services=import_services,
                    )
            else:
                if item["only_on_master"] and master:
                    self.populateService(
                        name,
                        master=master,
                        all_in_one=all_in_one,
                        import_services=import_services,
                    )
                elif not item["only_on_master"] and not master:
                    importService = item.get("import_service", False)
                    if (
                        importService and import_services
                    ) or not importService:
                        self.populateService(
                            name,
                            master=master,
                            all_in_one=all_in_one,
                            import_services=import_services,
                        )

    @asynchronous
    def prepare(self):
        """Perform start_up of the region process."""
        from maasserver.start_up import start_up

        self.logger.info("Calling start_up to start region process")
        return start_up(self.master)

    @asynchronous
    def startMultiService(self, result):
        """Start the multi service."""
        self.logger.info("Starting eventloop multiservice")
        self.services.startService()

    @asynchronous
    def start(self, master=False, all_in_one=False):
        """start()

        Start all services in the region's event-loop.
        """
        self.logger.info("Starting eventloop")
        self.populate(master=master, all_in_one=all_in_one)
        self.handle = reactor.addSystemEventTrigger(
            "before", "shutdown", self.services.stopService
        )
        d = self.prepare()
        d.addCallback(self.startMultiService)
        d.addCallback(call, logger.info, "Region started")
        return d

    @asynchronous
    def restart(self):
        """Convenience method that resets and starts event-loop."""
        self.logger.info("Restarting region")
        d = self.reset()
        d.addCallback(
            call, self.start, master=self.master, all_in_one=self.all_in_one
        )
        d.addCallback(call, self.logger.info, "Region restarted")
        return d

    @asynchronous
    def stop(self):
        """stop()

        Stop all services in the region's event-loop.
        """
        self.logger.info("Stopping region")
        if self.handle is not None:
            handle, self.handle = self.handle, None
            reactor.removeSystemEventTrigger(handle)
        return self.services.stopService()

    @asynchronous
    def reset(self):
        """reset()

        Stop all services, then disown them all.
        """

        def disown_all_services(_):
            for service in list(self.services):
                service.disownServiceParent()

        def reset_factories(_):
            try:
                # Unshadow class attribute.
                del self.factories
            except AttributeError:
                # It wasn't shadowed.
                pass

        self.logger.info("Resetting region")
        d = self.stop()
        d.addCallback(disown_all_services)
        d.addCallback(reset_factories)
        d.addCallback(call, self.logger.info, "Region reset finished")
        return d

    @property
    def name(self):
        """A name for identifying this service in a distributed system."""
        return "%s:pid=%d" % (gethostname(), os.getpid())

    @property
    def running(self):
        """Is this running?"""
        return bool(self.services.running)


loop = RegionEventLoop()
reset = loop.reset
services = loop.services
start = loop.start
stop = loop.stop
restart = loop.restart
