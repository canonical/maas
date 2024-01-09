# Copyright 2014-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Obtain list of boot images from rack controllers."""

__all__ = [
    "get_all_available_boot_images",
    "get_boot_images",
    "get_boot_images_for",
    "get_common_available_boot_images",
]

from functools import partial

from twisted.python.failure import Failure

from maasserver.models import BootResource
from maasserver.rpc import getAllClients, getClientFor
from maasserver.utils.asynchronous import gather
from provisioningserver.logger import LegacyLogger
from provisioningserver.rpc.cluster import ListBootImages
from provisioningserver.utils.twisted import synchronous

log = LegacyLogger()


def suppress_failures(responses):
    """Suppress failures returning from an async/gather operation.

    This may not be advisable! Be very sure this is what you want.
    """
    for response in responses:
        if not isinstance(response, Failure):
            yield response


# FIXME alexsander-souza: drop this
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
