# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Service to periodically refresh the boot images."""


from datetime import timedelta

from twisted.application.internet import TimerService
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.protocols.amp import UnhandledCommand

from provisioningserver.boot import tftppath
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rpc.boot_images import import_boot_images
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.rpc.region import (
    GetBootSources,
    GetBootSourcesV2,
    GetProxies,
)
from provisioningserver.utils.twisted import pause, retries

maaslog = get_maas_logger("boot_image_download_service")
log = LegacyLogger()


class ImageDownloadService(TimerService, object):
    """Twisted service to periodically refresh ephemeral images."""

    check_interval = timedelta(minutes=5).total_seconds()

    def __init__(self, client_service, tftp_root, reactor):
        """Twisted service to periodically refresh ephemeral images.

        :param client_service: A `ClusterClientService` instance.
        :param tftp_root: The path to the TFTP root directory.
        :param reactor: An `IReactor` instance.
        """
        super().__init__(self.check_interval, self.try_download)
        self.client_service = client_service
        self.tftp_root = tftp_root
        self.clock = reactor

    def try_download(self):
        """Wrap download attempts in something that catches Failures.

        Log the full error to the Twisted log, and a concise error to
        the maas log.
        """

        def download_failure(failure):
            log.err(failure, "Downloading images failed.")
            maaslog.error(
                "Failed to download images: %s", failure.getErrorMessage()
            )

        return self.maybe_start_download().addErrback(download_failure)

    @inlineCallbacks
    def _get_boot_sources(self, client):
        """Gets the boot sources from the region."""
        try:
            sources = yield client(GetBootSourcesV2, uuid=client.localIdent)
        except UnhandledCommand:
            # Region has not been upgraded to support the new call, use the
            # old call. The old call did not provide the new os selection
            # parameter. Region does not support boot source selection by os,
            # so its set too allow all operating systems.
            sources = yield client(GetBootSources, uuid=client.localIdent)
            for source in sources["sources"]:
                for selection in source["selections"]:
                    selection["os"] = "*"
        returnValue(sources)

    @inlineCallbacks
    def _start_download(self):
        client = None
        # Retry a few times, since this service usually comes up before
        # the RPC service.
        for elapsed, remaining, wait in retries(15, 5, self.clock):
            try:
                client = yield self.client_service.getClientNow()
                break
            except NoConnectionsAvailable:
                yield pause(wait, self.clock)
        else:
            maaslog.error(
                "Can't initiate image download, no RPC connection to region."
            )
            return

        # Get sources from region
        sources = yield self._get_boot_sources(client)
        # Get http proxy from region
        proxies = yield client(GetProxies)

        def get_proxy_url(scheme):
            url = proxies.get(scheme)  # url is a ParsedResult.
            return None if url is None else url.geturl()

        yield import_boot_images(
            sources.get("sources"),
            self.client_service.maas_url,
            get_proxy_url("http"),
            get_proxy_url("https"),
        )

    @inlineCallbacks
    def maybe_start_download(self):
        """Check the time the last image refresh happened and initiate a new
        one if older than 15 minutes.
        """
        last_modified = tftppath.maas_meta_last_modified(self.tftp_root)
        if last_modified is None:
            yield self._start_download()
        else:
            age_in_seconds = self.clock.seconds() - last_modified
            if age_in_seconds >= timedelta(minutes=15).total_seconds():
                yield self._start_download()
