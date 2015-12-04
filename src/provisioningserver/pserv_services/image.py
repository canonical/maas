# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin for the MAAS Boot Image server"""

__all__ = [
    "BootImageEndpointService",
    ]

from twisted.application.internet import StreamServerEndpointService
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.static import File


class BootImageEndpointService(StreamServerEndpointService):
    """Service for serving images to the TFTP server via HTTP

    :ivar site: The twisted site resource

    """

    def __init__(self, resource_root, endpoint):
        """
        :param resource_root: The root directory for the Image server.
        :param endpoint: The endpoint on which the server should listen.

        """
        resource = Resource()
        resource.putChild('images', File(resource_root))
        self.site = Site(resource)
        super(BootImageEndpointService, self).__init__(endpoint, self.site)
