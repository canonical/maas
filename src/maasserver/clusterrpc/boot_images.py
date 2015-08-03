# Copyright 2014 Canonical Ltd.  This software is licensed under the
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
    "get_available_boot_images",
    "get_boot_images",
    "get_boot_images_for",
    "is_import_boot_images_running",
    "is_import_boot_images_running_for",
]

from functools import partial
from itertools import imap

from maasserver.rpc import (
    getAllClients,
    getClientFor,
    )
from maasserver.utils import async
from provisioningserver.rpc.cluster import (
    IsImportBootImagesRunning,
    ListBootImages,
    ListBootImagesV2,
    )
from provisioningserver.utils.twisted import synchronous
from twisted.protocols.amp import UnhandledCommand
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
def get_available_boot_images():
    """Obtain boot images that are available on all clusters."""
    image_sets = list(_get_available_boot_images())
    if len(image_sets) > 0:
        images = frozenset.intersection(*image_sets)
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
