'''
@author: shylent
'''
from tftp.datagram import (ACKDatagram, ERRORDatagram, OP_DATA, OP_ERROR, ERR_ILLEGAL_OP,
    ERR_DISK_FULL, OP_ACK, DATADatagram, ERR_NOT_DEFINED,)
from tftp.util import SequentialCall
from twisted.internet import reactor
from twisted.internet.defer import maybeDeferred
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log

MAX_BLOCK_SIZE = 1400


class WriteSession(DatagramProtocol):
    """Represents a transfer, during which we write to a local file. If we are a
    server, this means, that we received a WRQ (write request). If we are a client,
    this means, that we have requested a read from a remote server.

    @cvar block_size: Expected block size. If a data chunk is received and its length
    is less, than C{block_size}, it is assumed that that data chunk is the last in the
    transfer. Default: 512 (as per U{RFC1350<http://tools.ietf.org/html/rfc1350>})
    @type block_size: C{int}.

    @cvar timeout: An iterable, that yields timeout values for every subsequent
    ACKDatagram, that we've sent, that is not followed by the next data chunk.
    When (if) the iterable is exhausted, the transfer is considered failed.
    @type timeout: any iterable

    @ivar started: whether or not this protocol has started
    @type started: C{bool}

    """

    block_size = 512
    timeout = (1, 3, 7)
    tsize = None

    def __init__(self, writer, _clock=None):
        self.writer = writer
        self.blocknum = 0
        self.completed = False
        self.started = False
        self.timeout_watchdog = None
        if _clock is None:
            self._clock = reactor
        else:
            self._clock = _clock

    def cancel(self):
        """Cancel this session, discard any data, that was collected
        and give up the connector.

        """
        if self.timeout_watchdog is not None and self.timeout_watchdog.active():
            self.timeout_watchdog.cancel()
        self.writer.cancel()
        self.transport.stopListening()

    def startProtocol(self):
        self.started = True

    def connectionRefused(self):
        if not self.completed:
            self.writer.cancel()
        self.transport.stopListening()

    def datagramReceived(self, datagram):
        if datagram.opcode == OP_DATA:
            return self.tftp_DATA(datagram)
        elif datagram.opcode == OP_ERROR:
            log.msg("Got error: %s" % datagram)
            self.cancel()

    def tftp_DATA(self, datagram):
        """Handle incoming DATA TFTP datagram

        @type datagram: L{DATADatagram}

        """
        next_blocknum = self.blocknum + 1
        if datagram.blocknum < next_blocknum:
            self.transport.write(ACKDatagram(datagram.blocknum).to_wire())
        elif datagram.blocknum == next_blocknum:
            if self.completed:
                self.transport.write(ERRORDatagram.from_code(
                    ERR_ILLEGAL_OP, "Transfer already finished").to_wire())
            else:
                return self.nextBlock(datagram)
        else:
            self.transport.write(ERRORDatagram.from_code(
                ERR_ILLEGAL_OP, "Block number mismatch").to_wire())

    def nextBlock(self, datagram):
        """Handle fresh data, attempt to write it to backend

        @type datagram: L{DATADatagram}

        """
        if self.timeout_watchdog is not None and self.timeout_watchdog.active():
            self.timeout_watchdog.cancel()
        self.blocknum += 1
        d = maybeDeferred(self.writer.write, datagram.data)
        d.addCallbacks(callback=self.blockWriteSuccess, callbackArgs=[datagram, ],
                       errback=self.blockWriteFailure)
        return d

    def blockWriteSuccess(self, ign, datagram):
        """The write was successful, respond with ACK for current block number

        If this is the last chunk (received data length < block size), the protocol
        will keep running until the end of current timeout period, so we can respond
        to any duplicates.

        @type datagram: L{DATADatagram}

        """
        bytes = ACKDatagram(datagram.blocknum).to_wire()
        self.timeout_watchdog = SequentialCall.run(self.timeout[:-1],
            callable=self.sendData, callable_args=[bytes, ],
            on_timeout=lambda: self._clock.callLater(self.timeout[-1], self.timedOut),
            run_now=True,
            _clock=self._clock
        )
        if len(datagram.data) < self.block_size:
            self.completed = True
            self.writer.finish()
            # TODO: If self.tsize is not None, compare it with the actual
            # count of bytes written. Log if there's a mismatch. Should it
            # also emit an error datagram?

    def blockWriteFailure(self, failure):
        """Write failed"""
        log.err(failure)
        self.transport.write(ERRORDatagram.from_code(ERR_DISK_FULL).to_wire())
        self.cancel()

    def timedOut(self):
        """Called when the protocol has timed out. Let the backend know, if the
        the transfer was successful.

        """
        if not self.completed:
            log.msg("Timed out while waiting for next block")
            self.writer.cancel()
        else:
            log.msg("Timed out after a successful transfer")
        self.transport.stopListening()

    def sendData(self, bytes):
        """Send data to the remote peer

        @param bytes: bytes to send
        @type bytes: C{str}

        """
        self.transport.write(bytes)


class ReadSession(DatagramProtocol):
    """Represents a transfer, during which we read from a local file
    (and write to the network). If we are a server, this means, that we've received
    a RRQ (read request). If we are a client, this means that we've requested to
    write to a remote server.

    @cvar block_size: The data will be sent in chunks of this size. If we send
    a chunk with the size < C{block_size}, the transfer will end.
    Default: 512 (as per U{RFC1350<http://tools.ietf.org/html/rfc1350>})
    @type block_size: C{int}

    @cvar timeout: An iterable, that yields timeout values for every subsequent
    unacknowledged DATADatagram, that we've sent. When (if) the iterable is exhausted,
    the transfer is considered failed.
    @type timeout: any iterable

    @ivar started: whether or not this protocol has started
    @type started: C{bool}

    """
    block_size = 512
    timeout = (1, 3, 7)

    def __init__(self, reader, _clock=None):
        self.reader = reader
        self.blocknum = 0
        self.started = False
        self.completed = False
        self.timeout_watchdog = None
        if _clock is None:
            self._clock = reactor
        else:
            self._clock = _clock

    def cancel(self):
        """Tell the reader to give up the resources. Stop the timeout cycle
        and disconnect the transport.

        """
        self.reader.finish()
        if self.timeout_watchdog is not None and self.timeout_watchdog.active():
            self.timeout_watchdog.cancel()
        self.transport.stopListening()

    def startProtocol(self):
        self.started = True

    def connectionRefused(self):
        self.finish()

    def datagramReceived(self, datagram):
        if datagram.opcode == OP_ACK:
            return self.tftp_ACK(datagram)
        elif datagram.opcode == OP_ERROR:
            log.msg("Got error: %s" % datagram)
            self.cancel()

    def tftp_ACK(self, datagram):
        """Handle the incoming ACK TFTP datagram.

        @type datagram: L{ACKDatagram}

        """
        if datagram.blocknum < self.blocknum:
            log.msg("Duplicate ACK for blocknum %s" % datagram.blocknum)
        elif datagram.blocknum == self.blocknum:
            if self.timeout_watchdog is not None and self.timeout_watchdog.active():
                self.timeout_watchdog.cancel()
            if self.completed:
                log.msg("Final ACK received, transfer successful")
                self.cancel()
            else:
                return self.nextBlock()
        else:
            self.transport.write(ERRORDatagram.from_code(
                ERR_ILLEGAL_OP, "Block number mismatch").to_wire())

    def nextBlock(self):
        """ACK datagram for the previous block has been received. Attempt to read
        the next block, that will be sent.

        """
        self.blocknum += 1
        d = maybeDeferred(self.reader.read, self.block_size)
        d.addCallbacks(callback=self.dataFromReader, errback=self.readFailed)
        return d

    def dataFromReader(self, data):
        """Got data from the reader. Send it to the network and start the timeout
        cycle.

        """
        if len(data) < self.block_size:
            self.completed = True
        bytes = DATADatagram(self.blocknum, data).to_wire()
        self.timeout_watchdog = SequentialCall.run(self.timeout[:-1],
            callable=self.sendData, callable_args=[bytes, ],
            on_timeout=lambda: self._clock.callLater(self.timeout[-1], self.timedOut),
            run_now=True,
            _clock=self._clock
        )

    def readFailed(self, fail):
        """The reader reported an error. Notify the remote end and cancel the transfer"""
        log.err(fail)
        self.transport.write(ERRORDatagram.from_code(ERR_NOT_DEFINED, "Read failed").to_wire())
        self.cancel()

    def timedOut(self):
        """Timeout iterable has been exhausted. End the transfer"""
        log.msg("Session timed out, last wait was %s seconds long" % self.timeout[-1])
        self.cancel()

    def sendData(self, bytes):
        """Send data to the remote peer

        @param bytes: bytes to send
        @type bytes: C{str}

        """
        self.transport.write(bytes)
