# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted service that periodically checks to see whether a routine download
of ephemeral images is required, and kicks off a thread to do so if needed.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "PeriodicImageDownloadService",
    ]


from datetime import timedelta

from provisioningserver.auth import MAAS_USER_GPGHOME
from provisioningserver.boot.tftppath import maas_meta_last_modified
from provisioningserver.import_images import boot_resources
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    GetBootSources,
    GetProxies,
    )
from provisioningserver.utils.env import environment_variables
from provisioningserver.utils.twisted import pause
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    DeferredLock,
    inlineCallbacks,
    )
from twisted.internet.threads import deferToThread


maaslog = get_maas_logger("image_download_service")
service_lock = DeferredLock()


def import_boot_images(sources, http_proxy=None, https_proxy=None):
    """Set up environment and run an import."""
    # Note that this is cargo-culted from provisioningserver.tasks. That
    # code cannot be imported because it is decorated with celery.task,
    # which pulls in celery config that doesn't exist in the pserv
    # environment.
    variables = {
        'GNUPGHOME': MAAS_USER_GPGHOME,
        }
    if http_proxy is not None:
        variables['http_proxy'] = http_proxy
    if https_proxy is not None:
        variables['https_proxy'] = https_proxy
    with environment_variables(variables):
        boot_resources.import_images(sources)


class PeriodicImageDownloadService(TimerService, object):
    """Twisted service to periodically refresh ephemeral images.

    :param client_service: A `ClusterClientService` instance for talking
        to the region controller.
    :param reactor: An `IReactor` instance.
    """

    check_interval = 3600  # In seconds, 1 hour.

    def __init__(self, client_service, reactor, cluster_uuid):
        # Call self.check() every self.check_interval.
        super(PeriodicImageDownloadService, self).__init__(
            self.check_interval, self.maybe_start_download)
        self.clock = reactor
        self.client_service = client_service
        self.uuid = cluster_uuid

    @inlineCallbacks
    def _start_download(self):
        client = None
        # Retry a few times, since this service usually comes up before
        # the RPC service.
        for _ in range(3):
            try:
                client = self.client_service.getClient()
                break
            except NoConnectionsAvailable:
                yield pause(5)
        if client is None:
            maaslog.error(
                "Can't initiate image download, no RPC connection to region.")
            return

        # Get sources from region
        sources = yield client(GetBootSources, uuid=self.uuid)
        # Get http proxy from region
        proxies = yield client(GetProxies)
        yield deferToThread(
            import_boot_images, sources.get("sources"),
            proxies.get('http_proxy'), proxies.get('https_proxy'))

    @inlineCallbacks
    def maybe_start_download(self):
        """Check the time the last image refresh happened and initiate a new
        one if older than a week.
        """
        # Use a DeferredLock to prevent simultaneous downloads.
        if service_lock.locked:
            # Don't want to block on lock release.
            return
        yield service_lock.acquire()
        try:
            last_modified = maas_meta_last_modified()
            if last_modified is None:
                # Don't auto-refresh if the user has never manually initiated
                # a download.
                return

            age_in_seconds = self.clock.seconds() - last_modified
            if age_in_seconds >= timedelta(weeks=1).total_seconds():
                yield self._start_download()

        finally:
            service_lock.release()
