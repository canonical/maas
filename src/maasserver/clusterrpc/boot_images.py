# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Obtain list of boot images from rack controllers."""

__all__ = [
    "RackControllersImporter",
    "get_all_available_boot_images",
    "get_boot_images",
    "get_boot_images_for",
    "get_common_available_boot_images",
    "is_import_boot_images_running",
]

from collections.abc import Sequence
from functools import partial
from urllib.parse import ParseResult, urlparse

from twisted.internet import reactor
from twisted.internet.defer import DeferredList, DeferredSemaphore
from twisted.python.failure import Failure

from maasserver.models import BootResource, RackController
from maasserver.rpc import getAllClients, getClientFor
from maasserver.utils.asynchronous import gather
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.cluster import (
    ImportBootImages,
    IsImportBootImagesRunning,
    ListBootImages,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils import flatten
from provisioningserver.utils.twisted import asynchronous, synchronous

log = LegacyLogger()


def suppress_failures(responses):
    """Suppress failures returning from an async/gather operation.

    This may not be advisable! Be very sure this is what you want.
    """
    for response in responses:
        if not isinstance(response, Failure):
            yield response


@synchronous
def is_import_boot_images_running():
    """Return True if any rack controller is currently import boot images."""
    responses = gather(
        partial(client, IsImportBootImagesRunning)
        for client in getAllClients()
    )

    # Only one rack controller needs to say its importing image, for this
    # method to return True. Must go through all responses so they are all
    # marked handled.
    running = False
    for response in suppress_failures(responses):
        running = running or response["running"]
    return running


@synchronous
def get_boot_images(rack_controller):
    """Obtain the avaliable boot images of this rack controller.

    :param rack_controller: The RackController.

    :raises NoConnectionsAvailable: When no connections to the rack controller
        are available for use.
    :raises crochet.TimeoutError: If a response has not been received within
        30 seconds.
    """
    client = getClientFor(rack_controller.system_id, timeout=1)
    call = client(ListBootImages)
    return call.wait(30).get("images")


@synchronous
def _get_available_boot_images():
    """Obtain boot images available on connected rack controllers."""

    def listimages(client):
        return partial(client, ListBootImages)

    clients = getAllClients()
    responses = gather(map(listimages, clients))
    for i, response in enumerate(responses):
        if not isinstance(response, Failure):
            # Convert each image to a frozenset of its items.
            yield frozenset(
                frozenset(image.items()) for image in response["images"]
            )


@synchronous
def get_common_available_boot_images():
    """Obtain boot images that are available on *all* rack controllers."""
    image_sets = list(_get_available_boot_images())
    if len(image_sets) > 0:
        images = frozenset.intersection(*image_sets)
    else:
        images = frozenset()
    # Return using the same format as get_boot_images.
    return list(dict(image) for image in images)


@synchronous
def get_all_available_boot_images():
    """Obtain boot images that are available on *any* rack controllers."""
    image_sets = list(_get_available_boot_images())
    if len(image_sets) > 0:
        images = frozenset.union(*image_sets)
    else:
        images = frozenset()
    # Return using the same format as get_boot_images.
    return list(dict(image) for image in images)


@synchronous
def get_boot_images_for(
    rack_controller, osystem, architecture, subarchitecture, series
):
    """Obtain the available boot images of this rack controller for the given
    osystem, architecture, subarchitecute, and series.

    :param rack_controller: The RackController.
    :param osystem: The operating system.
    :param architecture: The architecture.
    :param subarchitecute: The subarchitecute.
    :param series: The operating system series.

    :raises NoConnectionsAvailable: When no connections to the rack controller
        are available for use.
    :raises crochet.TimeoutError: If a response has not been received within
        30 seconds.
    """
    images = get_boot_images(rack_controller)
    images = [
        image
        for image in images
        if image["osystem"] == osystem
        and image["release"] == series
        and image["architecture"] == architecture
    ]

    # Subarchitecture can be different than what the rack controller sends
    # back. This is because of hwe kernels. If the image matches this far, then
    # we check its matching BootResource for all supported subarchitectures.
    matching_images = []
    for image in images:
        if image["subarchitecture"] == subarchitecture:
            matching_images.append(image)
        else:
            resource = BootResource.objects.get_resource_for(
                osystem, architecture, subarchitecture, series
            )
            if resource is not None:
                if "platform" in resource.extra:
                    image["platform"] = resource.extra["platform"]
                if "supported_platforms" in resource.extra:
                    image["supported_platforms"] = resource.extra[
                        "supported_platforms"
                    ]
                matching_images.append(image)
    return matching_images


undefined = object()


class RackControllersImporter:
    """Utility to help import boot resources from the region to rack
    controllers."""

    @staticmethod
    def _get_system_ids():
        racks = RackController.objects.all()
        system_ids = racks.values_list("system_id", flat=True)
        return list(system_ids)

    @staticmethod
    def _get_sources():
        # Avoid circular import.
        from maasserver.bootresources import get_simplestream_endpoint

        endpoint = get_simplestream_endpoint()
        return [endpoint]

    @staticmethod
    def _get_proxy():
        # Avoid circular import.
        from maasserver.models.config import Config

        if Config.objects.get_config("enable_http_proxy"):
            return Config.objects.get_config("http_proxy")
        else:
            return None

    @classmethod
    @transactional
    def new(cls, system_ids=undefined, sources=undefined, proxy=undefined):
        """Create a new importer.

        Obtain values for `system_ids`, `sources` and `proxy` if they're not
        provided. This MUST be called in a database thread.

        :return: :class:`RackControllersImporter`
        """
        return cls(
            cls._get_system_ids() if system_ids is undefined else system_ids,
            cls._get_sources() if sources is undefined else sources,
            cls._get_proxy() if proxy is undefined else proxy,
        )

    @classmethod
    def schedule(
        cls,
        system_ids=undefined,
        sources=undefined,
        proxy=undefined,
        concurrency=1,
        delay=0,
        clock=reactor,
    ):
        """Schedule rack controller imports to happen."""

        def do_import():
            d = deferToDatabase(
                RackControllersImporter.new, system_ids, sources, proxy
            )
            d.addCallback(lambda importer: importer.run(concurrency))
            return d

        return clock.callLater(delay, do_import)

    def __init__(self, system_ids, sources, proxy=None):
        """Create a new importer.

        :param system_ids: A sequence of rack controller system_id's.
        :param sources: A sequence of endpoints; see `ImportBootImages`.
        :param proxy: The HTTP/HTTPS proxy to use, or `None`
        :type proxy: :class:`urlparse.ParseResult` or string
        """
        super().__init__()
        self.system_ids = tuple(flatten(system_ids))
        if isinstance(sources, Sequence):
            self.sources = sources
        else:
            raise TypeError(f"expected sequence, got: {sources!r}")
        if proxy is None or isinstance(proxy, ParseResult):
            self.proxy = proxy
        else:
            self.proxy = urlparse(proxy)

    @asynchronous
    def __call__(self, lock):
        """Ask the rack controllers to download the region's boot resources.

        :param lock: A concurrency primitive to limit the number of rack
            controllers importing at one time.
        """

        def sync_rack(system_id, sources, proxy):
            d = getClientFor(system_id, timeout=1)
            d.addCallback(
                lambda client: client(
                    ImportBootImages,
                    sources=sources,
                    http_proxy=proxy,
                    https_proxy=proxy,
                )
            )
            return d

        return DeferredList(
            (
                lock.run(sync_rack, system_id, self.sources, self.proxy)
                for system_id in self.system_ids
            ),
            consumeErrors=True,
        )

    @asynchronous
    def run(self, concurrency=1):
        """Ask the rack controllers to download the region's boot resources.

        Report the results via the log.

        :param concurrency: Limit the number of rack controllers importing at
            one time to no more than `concurrency`.
        """
        lock = DeferredSemaphore(concurrency)

        def report(results):
            message_success = (
                "Rack controller (%s) has imported boot resources."
            )
            message_failure = (
                "Rack controller (%s) failed to import boot resources."
            )
            message_disconn = (
                "Rack controller (%s) did not import boot resources; it is "
                "not connected to the region at this time."
            )
            for system_id, (success, result) in zip(self.system_ids, results):
                if success:
                    log.msg(message_success % system_id)
                elif result.check(NoConnectionsAvailable):
                    log.msg(message_disconn % system_id)
                else:
                    log.err(result, message_failure % system_id)

        return (
            self(lock)
            .addCallback(report)
            .addErrback(log.err, "General failure syncing boot resources.")
        )
