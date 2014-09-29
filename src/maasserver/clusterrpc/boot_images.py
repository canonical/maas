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
    "get_boot_images",
    "get_boot_images_for",
    "is_import_boot_images_running",
]

from maasserver.rpc import getClientFor
from provisioningserver.rpc.cluster import (
    IsImportBootImagesRunning,
    ListBootImages,
    )
from provisioningserver.utils.twisted import synchronous


@synchronous
def is_import_boot_images_running(nodegroup):
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
