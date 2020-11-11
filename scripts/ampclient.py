# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Example code for an AMP client to call into MAAS."""



import sys

from provisioningserver.rpc.cluster import ListBootImages
from provisioningserver.rpc.region import ReportBootImages
from twisted.internet import reactor
from twisted.internet.endpoints import (
    connectProtocol,
    TCP4ClientEndpoint,
)
from twisted.protocols.amp import AMP


def callRemote(command, port, **kwargs):
    dest = TCP4ClientEndpoint(reactor, '127.0.0.1', port)
    d = connectProtocol(dest, AMP())

    def connected(ampProto):
        return ampProto.callRemote(command, **kwargs)

    return d.addCallback(connected)


def listBootImages():
    return callRemote(ListBootImages, 5248)


def reportBootImages(port):
    return callRemote(ReportBootImages, port, uuid="foobar", images=[])


if __name__ == '__main__':
    # d = listBootImages()
    d = reportBootImages(int(sys.argv[1]))

    def done(result):
        print(result)
        reactor.stop()
    d.addBoth(done)

    reactor.run()
