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

from maasserver.rpc import (
    getAllClients,
    getClientFor,
)
from maasserver.utils import async
from provisioningserver.rpc.cluster import (
    IsImportBootImagesRunning,
    ListBootImages,
)
from provisioningserver.utils.twisted import synchronous
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
    call = client(ListBootImages)
    return call.wait(30).get("images")


@synchronous
def get_available_boot_images():
    """Obtain boot images that are available on all clusters."""
    responses = async.gather(
        partial(client, ListBootImages)
        for client in getAllClients())
    responses = [
        response["images"]
        for response in suppress_failures(responses)
        ]
    if len(responses) == 0:
        return []

    # Create the initial set of images from the first response. This will be
    # used to perform the intersection of all the other responses.
    images = responses.pop()
    images = {
        frozenset(image.items())
        for image in images
        }

    # Intersect all of the remaining responses to get only the images that
    # exist on all clusters.
    for response in responses:
        response_images = {
            frozenset(image.items())
            for image in response
            }
        images = images & response_images

    # Return only boot images on all cluster, in the same format as
    # get_boot_images.
    return [
        dict(image)
        for image in list(images)
        ]


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
