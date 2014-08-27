# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically refresh the boot images."""

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

from provisioningserver.boot import tftppath
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.boot_images import import_boot_images
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    GetBootSources,
    GetBootSourcesV2,
    )
from provisioningserver.utils.twisted import pause
from twisted.application.internet import TimerService
from twisted.internet.defer import (
    DeferredLock,
    inlineCallbacks,
    returnValue,
    )
from twisted.spread.pb import NoSuchMethod


maaslog = get_maas_logger("boot_image_download_service")
service_lock = DeferredLock()


class PeriodicImageDownloadService(TimerService, object):
    """Twisted service to periodically refresh ephemeral images.

    :param client_service: A `ClusterClientService` instance for talking
        to the region controller.
    :param reactor: An `IReactor` instance.
    """

    check_interval = timedelta(minutes=5).total_seconds()

    def __init__(self, client_service, reactor, cluster_uuid):
        # Call self.check() every self.check_interval.
        super(PeriodicImageDownloadService, self).__init__(
            self.check_interval, self.maybe_start_download)
        self.clock = reactor
        self.client_service = client_service
        self.uuid = cluster_uuid

    @inlineCallbacks
    def _get_boot_sources(self, client):
        """Gets the boot sources from the region."""
        try:
            sources = yield client(GetBootSourcesV2, uuid=self.uuid)
        except NoSuchMethod:
            # Region has not been upgraded to support the new call, use the
            # old call. The old call did not provide the new os selection
            # parameter. Region does not support boot source selection by os,
            # so its set too allow all operating systems.
            sources = yield client(GetBootSources, uuid=self.uuid)
            for source in sources['sources']:
                for selection in source['selections']:
                    selection['os'] = '*'
        returnValue(sources)

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
        sources = yield self._get_boot_sources(client)
        yield import_boot_images(sources.get("sources"))

    @inlineCallbacks
    def maybe_start_download(self):
        """Check the time the last image refresh happened and initiate a new
        one if older than 15 minutes.
        """
        # Use a DeferredLock to prevent simultaneous downloads.
        if service_lock.locked:
            # Don't want to block on lock release.
            return
        yield service_lock.acquire()
        try:
            last_modified = tftppath.maas_meta_last_modified()
            if last_modified is None:
                # Don't auto-refresh if the user has never manually initiated
                # a download.
                return

            age_in_seconds = self.clock.seconds() - last_modified
            if age_in_seconds >= timedelta(minutes=15).total_seconds():
                yield self._start_download()

        finally:
            service_lock.release()
