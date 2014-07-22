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
__all__ = []


from datetime import timedelta
from logging import getLogger

from provisioningserver.boot.tftppath import maas_meta_last_modified
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    GetBootSources,
    GetProxies,
    )
from provisioningserver.tasks import import_boot_images
from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks
from twisted.internet.threads import deferToThread


logger = getLogger(__name__)


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
        try:
            client = self.client_service.getClient()
        except NoConnectionsAvailable:
            logger.error(
                "Can't initiate image download, no RPC connection to region.")
            return

        # Get sources from region
        sources = yield client(GetBootSources, uuid=self.uuid)
        # Get http proxy from region
        proxies = yield client(GetProxies)
        yield deferToThread(
            import_boot_images, sources, proxies['http_proxy'])

    def maybe_start_download(self):
        """Check the time the last image refresh happened and initiate a new
        one if older than a week.
        """
        last_modified = maas_meta_last_modified()
        if last_modified is None:
            # Don't auto-refresh if the user has never manually initiated
            # a download.
            return

        age_in_seconds = self.clock.seconds() - last_modified
        if age_in_seconds >= timedelta(weeks=1).total_seconds():
            return self._start_download()

        # Nothing to do otherwise.
