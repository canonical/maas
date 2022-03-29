# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""TFTP offload server.

  ********************
  **                **
  **  EXPERIMENTAL  **
  **                **
  ********************

"""


import os
import shutil
import tempfile

import tftp.backend
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import interfaces, protocol
from twisted.internet.defer import inlineCallbacks, maybeDeferred
from twisted.python import context
from twisted.python.filepath import FilePath
from zope.interface import implementer

from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import call, callOut

log = LegacyLogger()


class TFTPOffloadService(StreamServerEndpointService):
    """Service for `TFTPOffloadProtocol` on a given endpoint."""

    def __init__(self, reactor, endpoint, backend):
        """
        :param reactor: A Twisted reactor.
        :param endpoint: A Twisted endpoint.
        :param backend: An instance of `TFTPBackend`.
        """
        super().__init__(endpoint, TFTPOffloadProtocolFactory(backend))


@implementer(interfaces.IProtocolFactory)
class TFTPOffloadProtocolFactory:
    """Factory for `TFTPOffloadProtocol`.

    This arranges a "hand-off" store (i.e. a temporary directory) that is used
    by the protocol to give ephemeral files to the offload process, which is
    then responsible for deleting them. This temporary directory will also be
    removed during shutdown of this factory so belt-n-braces.
    """

    def __init__(self, backend):
        super().__init__()
        self.backend = backend

    def buildProtocol(self, addr):
        return TFTPOffloadProtocol(self.backend, self.store)

    def doStart(self):
        self.store = tempfile.mkdtemp(prefix="maas.tftp.", suffix=".store")

    def doStop(self):
        store, self.store = self.store, None
        shutil.rmtree(store)


class TFTPOffloadProtocol(protocol.Protocol):
    """A partially dynamic read-only TFTP **offload** protocol.

    The protocol is simple. Where applicable and unless noted otherwise,
    values are encoded as ASCII.

    - On a new connection, write the following:

      - The local IP address
      - NULL (a single byte of value zero)
      - The remote IP address
      - NULL
      - The requested file name
      - NULL
      - A literal dollar sign

    - In response the following will be written:

      - A hyphen to indicate success
      - NULL
      - Either a hyphen or "EPH" to indicate the type of response
      - NULL
      - The file name to serve (in file-system encoding)
      - NULL
      - A literal dollar sign

      The offload process should then:

      - Serve the file specified to its client
      - Where "EPH" was specified, delete the file

    - Or, in the case of failure:

      - A decimal in ASCII denoting a TFTP error code
      - NULL
      - An error message encoded as UTF-8
      - NULL
      - A literal dollar sign

      The offload process should then:

      - Send an error packet to its client
      - Terminate the transfer

    """

    def __init__(self, backend, store):
        """
        :param backend: An instance of `TFTPBackend`.
        """
        super().__init__()
        self.backend = backend
        self.store = store

    def connectionMade(self):
        self.buf = b""

    def dataReceived(self, data):
        self.buf += data
        parts = self.buf.split(b"\x00")
        if len(parts) >= 4:
            self.prepareResponse(*parts)

    def prepareResponse(self, local, remote, file_name, over, *rest):
        if over != b"$":
            log.error(
                "Message not properly terminated: local={local!r} "
                "remote={remote!r} file_name={file_name!r} over={over!r} "
                "rest={rest!r}",
                local=local,
                remote=remote,
                file_name=file_name,
                over=over,
                rest=rest,
            )
            self.transport.loseConnection()
        elif len(rest) != 0:
            log.error(
                "Message had trailing garbage: local={local!r} "
                "remote={remote!r} file_name={file_name!r} over={over!r} "
                "rest={rest!r}",
                local=local,
                remote=remote,
                file_name=file_name,
                over=over,
                rest=rest,
            )
            self.transport.loseConnection()
        else:
            d = context.call(
                {"local": (local.decode(), 0), "remote": (remote.decode(), 0)},
                self.backend.get_reader,
                file_name,
            )
            d.addCallbacks(self.prepareWriteResponse, self.writeError)
            d.addBoth(call, self.transport.loseConnection)
            d.addErrback(log.err, "Failure in TFTP back-end.")

    def prepareWriteResponse(self, reader):
        if isinstance(reader, tftp.backend.FilesystemReader):
            d = maybeDeferred(self.writeFileResponse, reader)
        else:
            d = maybeDeferred(self.writeStreamedResponse, reader)
        return d.addBoth(callOut, reader.finish)

    def writeFileResponse(self, reader):
        return self.writeResponse(reader.file_path, ephemeral=False)

    def writeStreamedResponse(self, reader):
        return self.copyReader(reader).addCallback(
            self.writeResponse, ephemeral=True
        )

    @inlineCallbacks
    def copyReader(self, reader):
        tempfd, tempname = tempfile.mkstemp(dir=self.store)
        with os.fdopen(tempfd, "wb") as tempfd:
            chunksize = 2**16  # 64kiB
            while True:
                chunk = yield reader.read(chunksize)
                tempfd.write(chunk)
                if len(chunk) < chunksize:
                    return FilePath(tempname)

    def writeResponse(self, file_path, *, ephemeral):
        self.transport.write(b"-\x00")  # Hyphen = okay.
        self.transport.write(b"EPH\x00" if ephemeral else b"-\x00")
        self.transport.write(file_path.asBytesMode().path)
        self.transport.write(b"\x00$")  # Terminate. We're done.
        self.transport.loseConnection()

    def writeError(self, failure):
        # Use TFTP error codes where possible.
        self.transport.write(b"0\x00")  # 0 = See error message.
        self.transport.write(failure.getErrorMessage().encode())
        self.transport.write(b"\x00$")  # Terminate. We're done.
