# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for clusters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "ClusterService",
]

from provisioningserver.config import Config
from provisioningserver.pxe import tftppath
from provisioningserver.rpc import cluster
from twisted.application.internet import StreamServerEndpointService
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols import amp


class Cluster(amp.AMP):

    @cluster.ListBootImages.responder
    def list_boot_images(self):
        images = tftppath.list_boot_images(
            Config.load_from_cache()['tftp']['root'])
        return {"images": images}


class ClusterFactory(Factory):

    protocol = Cluster


class ClusterService(StreamServerEndpointService):

    def __init__(self, reactor, port):
        super(ClusterService, self).__init__(
            TCP4ServerEndpoint(reactor, port), ClusterFactory())
