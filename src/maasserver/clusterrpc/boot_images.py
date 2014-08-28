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
]

from maasserver.rpc import getClientFor
from provisioningserver.rpc.cluster import ListBootImages
from provisioningserver.utils.twisted import synchronous


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
