# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Obtain list of boot images from cluster."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClustersImporter",
    "get_all_available_boot_images",
    "get_boot_images",
    "get_boot_images_for",
    "get_common_available_boot_images",
    "is_import_boot_images_running",
    "is_import_boot_images_running_for",
]

from collections import Sequence
from functools import partial
from itertools import (
    imap,
    izip,
)
from urlparse import (
    ParseResult,
    urlparse,
)

from maasserver.rpc import (
    getAllClients,
    getClientFor,
)
from maasserver.utils import async
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.rpc.cluster import (
    ImportBootImages,
    IsImportBootImagesRunning,
    ListBootImages,
    ListBootImagesV2,
)
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.utils import flatten
from provisioningserver.utils.twisted import (
    asynchronous,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import (
    DeferredList,
    DeferredSemaphore,
)
from twisted.protocols.amp import UnhandledCommand
from twisted.python import log
from twisted.python.failure import Failure


def suppress_failures(responses):
    """Suppress failures returning from an async/gather operation.

    This may not be advisable! Be very sure this is what you want.
    """
    for response in responses:
        if not isinstance(response, Failure):
            yield response


@synchronous
def is_import_boot_images_running():
    """Return True if any cluster is currently import boot images."""
    responses = async.gather(
        partial(client, IsImportBootImagesRunning)
        for client in getAllClients())

    # Only one cluster needs to say its importing image, for this method to
    # return True. Must go through all responses so they are all
    # marked handled.
    running = False
    for response in suppress_failures(responses):
        running = running or response["running"]
    return running


@synchronous
def is_import_boot_images_running_for(nodegroup):
    """Return True if the cluster is currently import boot images.

    :param nodegroup: The nodegroup.

    :raises NoConnectionsAvailable: When no connections to the node's
        cluster are available for use.
    :raises crochet.TimeoutError: If a response has not been received within
        30 seconds.
    """
    client = getClientFor(nodegroup.uuid, timeout=1)
    call = client(IsImportBootImagesRunning)
    return call.wait(30).get("running")


@synchronous
def get_boot_images(nodegroup):
    """Obtain the avaliable boot images of this cluster.

    :param nodegroup: The nodegroup.

    :raises NoConnectionsAvailable: When no connections to the node's
        cluster are available for use.
    :raises crochet.TimeoutError: If a response has not been received within
        30 seconds.
    """
    client = getClientFor(nodegroup.uuid, timeout=1)
    try:
        call = client(ListBootImagesV2)
        return call.wait(30).get("images")
    except UnhandledCommand:
        call = client(ListBootImages)
        return call.wait(30).get("images")


@synchronous
def _get_available_boot_images():
    """Obtain boot images available on connected clusters."""
    listimages_v1 = lambda client: partial(client, ListBootImages)
    listimages_v2 = lambda client: partial(client, ListBootImagesV2)
    clients_v2 = getAllClients()
    responses_v2 = async.gather(imap(listimages_v2, clients_v2))
    clients_v1 = []
    for i, response in enumerate(responses_v2):
        if (isinstance(response, Failure) and
                response.check(UnhandledCommand) is not None):
            clients_v1.append(clients_v2[i])
        elif not isinstance(response, Failure):
            # Convert each image to a frozenset of its items.
            yield frozenset(
                frozenset(image.viewitems())
                for image in response["images"]
            )
    responses_v1 = async.gather(imap(listimages_v1, clients_v1))
    for response in suppress_failures(responses_v1):
        # Convert each image to a frozenset of its items.
        yield frozenset(
            frozenset(image.viewitems())
            for image in response["images"]
        )


@synchronous
def get_common_available_boot_images():
    """Obtain boot images that are available on *all* clusters."""
    image_sets = list(_get_available_boot_images())
    if len(image_sets) > 0:
        images = frozenset.intersection(*image_sets)
    else:
        images = frozenset()
    # Return using the same format as get_boot_images.
    return list(dict(image) for image in images)


@synchronous
def get_all_available_boot_images():
    """Obtain boot images that are available on *any* clusters."""
    image_sets = list(_get_available_boot_images())
    if len(image_sets) > 0:
        images = frozenset.union(*image_sets)
    else:
        images = frozenset()
    # Return using the same format as get_boot_images.
    return list(dict(image) for image in images)


@synchronous
def get_boot_images_for(
        nodegroup, osystem, architecture, subarchitecture, series):
    """Obtain the available boot images of this cluster for the given
    osystem, architecture, subarchitecute, and series.

    :param nodegroup: The nodegroup.
    :param osystem: The operating system.
    :param architecture: The architecture.
    :param subarchitecute: The subarchitecute.
    :param series: The operating system series.

    :raises NoConnectionsAvailable: When no connections to the node's
        cluster are available for use.
    :raises crochet.TimeoutError: If a response has not been received within
        30 seconds.
    """
    # Avoid circular imports when running the Node view tests in isolation.
    from maasserver.models import BootResource

    images = get_boot_images(nodegroup)
    images = [
        image
        for image in images
        if image['osystem'] == osystem and
        image['release'] == series and
        image['architecture'] == architecture
        ]

    # Subarchitecture can be different than what the cluster sends back. This
    # is because of hwe kernels. If the image matches this far, then we check
    # its matching BootResource for all supported subarchitectures.
    matching_images = []
    for image in images:
        if image['subarchitecture'] == subarchitecture:
            matching_images.append(image)
        else:
            resource = BootResource.objects.get_resource_for(
                osystem, architecture, subarchitecture, series)
            if resource is not None:
                matching_images.append(image)
    return matching_images


undefined = object()


class ClustersImporter:
    """Utility to help import boot resources from the region to clusters."""

    @staticmethod
    def _get_uuids():
        # Avoid circular import.
        from maasserver.enum import NODEGROUP_STATUS
        from maasserver.models import NodeGroup

        enabled = NODEGROUP_STATUS.ENABLED
        clusters = NodeGroup.objects.filter(status=enabled)
        uuids = clusters.values_list("uuid", flat=True)
        return list(uuids)

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
    def new(cls, uuids=undefined, sources=undefined, proxy=undefined):
        """Create a new importer.

        Obtain values for `uuids`, `sources` and `proxy` if they're not
        provided. This MUST be called in a database thread.

        :return: :class:`ClustersImporter`
        """
        return cls(
            cls._get_uuids() if uuids is undefined else uuids,
            cls._get_sources() if sources is undefined else sources,
            cls._get_proxy() if proxy is undefined else proxy,
        )

    @classmethod
    def schedule(
            cls, uuids=undefined, sources=undefined, proxy=undefined,
            concurrency=1, delay=0, clock=reactor):
        """Schedule cluster imports to happen."""

        def do_import():
            d = deferToDatabase(ClustersImporter.new, uuids, sources, proxy)
            d.addCallback(lambda importer: importer.run(concurrency))
            return d

        return clock.callLater(delay, do_import)

    def __init__(self, uuids, sources, proxy=None):
        """Create a new importer.

        :param uuids: A sequence of cluster UUIDs.
        :param sources: A sequence of endpoints; see `ImportBootImages`.
        :param proxy: The HTTP/HTTPS proxy to use, or `None`
        :type proxy: :class:`urlparse.ParseResult` or string
        """
        super(ClustersImporter, self).__init__()
        self.uuids = tuple(flatten(uuids))
        if isinstance(sources, Sequence):
            self.sources = sources
        else:
            raise TypeError("expected sequence, got: %r" % (sources,))
        if proxy is None or isinstance(proxy, ParseResult):
            self.proxy = proxy
        else:
            self.proxy = urlparse(proxy)

    @asynchronous
    def __call__(self, lock):
        """Ask the clusters to download the region's boot resources.

        :param lock: A concurrency primitive to limit the number of clusters
            importing at one time.
        """
        def sync_cluster(uuid, sources, proxy):
            d = getClientFor(uuid, timeout=1)
            d.addCallback(lambda client: client(
                ImportBootImages, sources=sources,
                http_proxy=proxy, https_proxy=proxy))
            return d

        return DeferredList(
            (lock.run(sync_cluster, uuid, self.sources, self.proxy)
             for uuid in self.uuids),
            consumeErrors=True)

    @asynchronous
    def run(self, concurrency=1):
        """Ask the clusters to download the region's boot resources.

        Report the results via the log.

        :param concurrency: Limit the number of clusters importing at one
            time to no more than `concurrency`.
        """
        lock = DeferredSemaphore(concurrency)

        def report(results):
            message_success = "Cluster (%s) has imported boot resources."
            message_failure = "Cluster (%s) failed to import boot resources."
            message_disconn = (
                "Cluster (%s) did not import boot resources; it is not "
                "connected to the region at this time."
            )
            for uuid, (success, result) in izip(self.uuids, results):
                if success:
                    log.msg(message_success % uuid)
                elif result.check(NoConnectionsAvailable):
                    log.msg(message_disconn % uuid)
                else:
                    log.err(result, message_failure % uuid)

        return self(lock).addCallback(report).addErrback(
            log.err, "General failure syncing boot resources.")
