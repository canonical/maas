# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `BootImage`."""

__all__ = [
    'BootImagesHandler',
    ]

from crochet import TimeoutError
from django.shortcuts import get_object_or_404
from maasserver.api.support import OperationsHandler
from maasserver.clusterrpc.boot_images import get_boot_images
from maasserver.exceptions import ClusterUnavailable
from maasserver.models import NodeGroup
from provisioningserver.rpc.exceptions import NoConnectionsAvailable


class BootImagesHandler(OperationsHandler):
    """Manage the collection of boot images."""
    api_doc_section_name = "Boot images"

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls, nodegroup=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        return ('boot_images_handler', [uuid])

    def read(self, request, uuid):
        """List boot images.

        Get a listing of a cluster's boot images.

        :param uuid: The UUID of the cluster for which the images
            should be listed.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        try:
            images = get_boot_images(nodegroup)
        except (NoConnectionsAvailable, TimeoutError):
            raise ClusterUnavailable()
        # Remove xinstall_type and xinstall_path as they are only
        # used internally.
        for image in images:
            del image['xinstall_path']
            del image['xinstall_type']
        return images
