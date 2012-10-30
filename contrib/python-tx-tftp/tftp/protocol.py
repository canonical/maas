'''
@author: shylent
'''
from tftp.bootstrap import RemoteOriginWriteSession, RemoteOriginReadSession
from tftp.datagram import (TFTPDatagramFactory, split_opcode, OP_WRQ,
    ERRORDatagram, ERR_NOT_DEFINED, ERR_ACCESS_VIOLATION, ERR_FILE_EXISTS,
    ERR_ILLEGAL_OP, OP_RRQ, ERR_FILE_NOT_FOUND)
from tftp.errors import (FileExists, Unsupported, AccessViolation, BackendError,
    FileNotFound)
from tftp.netascii import NetasciiReceiverProxy, NetasciiSenderProxy
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log
from twisted.python.context import call


class TFTP(DatagramProtocol):
    """TFTP dispatch protocol. Handles read requests (RRQ) and write requests (WRQ)
    and starts the corresponding sessions.

    @ivar backend: an L{IBackend} provider, that will handle interaction with
    local resources
    @type backend: L{IBackend} provider

    """
    def __init__(self, backend, _clock=None):
        self.backend = backend
        if _clock is None:
            self._clock = reactor
        else:
            self._clock = _clock

    def startProtocol(self):
        addr = self.transport.getHost()
        log.msg("TFTP Listener started at %s:%s" % (addr.host, addr.port))

    def datagramReceived(self, datagram, addr):
        datagram = TFTPDatagramFactory(*split_opcode(datagram))
        log.msg("Datagram received from %s: %s" % (addr, datagram))

        mode = datagram.mode.lower()
        if datagram.mode not in ('netascii', 'octet'):
            return self.transport.write(ERRORDatagram.from_code(ERR_ILLEGAL_OP,
                "Unknown transfer mode %s, - expected "
                "'netascii' or 'octet' (case-insensitive)" % mode).to_wire(), addr)

        self._clock.callLater(0, self._startSession, datagram, addr, mode)

    @inlineCallbacks
    def _startSession(self, datagram, addr, mode):
        # Set up a call context so that we can pass extra arbitrary
        # information to interested backends without adding extra call
        # arguments, or switching to using a request object, for example.
        context = {}
        if self.transport is not None:
            # Add the local and remote addresses to the call context.
            local = self.transport.getHost()
            context["local"] = local.host, local.port
            context["remote"] = addr
        try:
            if datagram.opcode == OP_WRQ:
                fs_interface = yield call(
                    context, self.backend.get_writer, datagram.filename)
            elif datagram.opcode == OP_RRQ:
                fs_interface = yield call(
                    context, self.backend.get_reader, datagram.filename)
        except Unsupported, e:
            self.transport.write(ERRORDatagram.from_code(ERR_ILLEGAL_OP,
                                    str(e)).to_wire(), addr)
        except AccessViolation:
            self.transport.write(ERRORDatagram.from_code(ERR_ACCESS_VIOLATION).to_wire(), addr)
        except FileExists:
            self.transport.write(ERRORDatagram.from_code(ERR_FILE_EXISTS).to_wire(), addr)
        except FileNotFound:
            self.transport.write(ERRORDatagram.from_code(ERR_FILE_NOT_FOUND).to_wire(), addr)
        except BackendError, e:
            self.transport.write(ERRORDatagram.from_code(ERR_NOT_DEFINED, str(e)).to_wire(), addr)
        else:
            if datagram.opcode == OP_WRQ:
                if mode == 'netascii':
                    fs_interface = NetasciiReceiverProxy(fs_interface)
                session = RemoteOriginWriteSession(addr, fs_interface,
                                                   datagram.options, _clock=self._clock)
                reactor.listenUDP(0, session)
                returnValue(session)
            elif datagram.opcode == OP_RRQ:
                if mode == 'netascii':
                    fs_interface = NetasciiSenderProxy(fs_interface)
                session = RemoteOriginReadSession(addr, fs_interface,
                                                  datagram.options, _clock=self._clock)
                reactor.listenUDP(0, session)
                returnValue(session)
