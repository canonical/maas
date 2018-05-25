# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""
HTTP static-file server.
"""

from errno import ENOPROTOOPT
import socket
from socket import error as socket_error

from provisioningserver.utils.twisted import reducedWebLogFormatter
from twisted.application.internet import StreamServerEndpointService
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.static import File


class EndpointService(StreamServerEndpointService):
    """Service for serving files via HTTP

    :ivar site: The twisted site resource

    """

    def __init__(self, resource_root, endpoint, prefix=None):
        """
        :param resource_root: The root directory for the Image server.
        :param endpoint: The endpoint on which the server should listen.

        """
        if prefix:
            resource = Resource()
            resource.putChild(prefix.encode('ascii'), File(resource_root))
        else:
            resource = File(resource_root)
        self.site = Site(resource, logFormatter=reducedWebLogFormatter)
        super(EndpointService, self).__init__(endpoint, self.site)


def create_reuse_socket():
    """
    Make a socket with SO_REUSEPORT set so that we can run multiple
    applications.
    """
    s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except socket_error as e:
        # Python's socket module was compiled using modern headers
        # thus defining SO_REUSEPORT would cause issues as it might
        # running in older kernel that does not support SO_REUSEPORT.

        # XXX andreserl 2015-04-08 bug=1441684: We need to add a warning
        # log message when we see this error, and a test for it.
        if e.errno != ENOPROTOOPT:
            raise e
    return s
