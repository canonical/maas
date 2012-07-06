'''
@author: shylent
'''
from tftp.datagram import (ACKDatagram, ERRORDatagram, ERR_TID_UNKNOWN,
    TFTPDatagramFactory, split_opcode, OP_OACK, OP_ERROR, OACKDatagram, OP_ACK,
    OP_DATA)
from tftp.session import WriteSession, MAX_BLOCK_SIZE, ReadSession
from tftp.util import SequentialCall
from twisted.internet import reactor
from twisted.internet.protocol import DatagramProtocol
from twisted.python import log
from twisted.python.util import OrderedDict

class TFTPBootstrap(DatagramProtocol):
    """Base class for TFTP Bootstrap classes, classes, that handle initial datagram
    exchange (option negotiation, etc), before the actual transfer is started.

    Why OrderedDict and not the regular one? As per
    U{RFC2347<http://tools.ietf.org/html/rfc2347>}, the order of options is, indeed,
    not important, but having them in an arbitrary order would complicate testing.

    @cvar supported_options: lists options, that we know how to handle

    @ivar session: A L{WriteSession} or L{ReadSession} object, that will handle
    the actual tranfer, after the initial handshake and option negotiation is
    complete
    @type session: L{WriteSession} or L{ReadSession}

    @ivar options: a mapping of options, that this protocol instance was
    initialized with. If it is empty and we are the server, usual logic (that
    doesn't involve OACK datagrams) is used.
    Default: L{OrderedDict<twisted.python.util.OrderedDict>}.
    @type options: L{OrderedDict<twisted.python.util.OrderedDict>}

    @ivar resultant_options: stores the last options mapping value, that was passed
    from the remote peer
    @type resultant_options: L{OrderedDict<twisted.python.util.OrderedDict>}

    @ivar remote: remote peer address
    @type remote: C{(str, int)}

    @ivar timeout_watchdog: an object, that is responsible for timing the protocol
    out. If we are initiating the transfer, it is provided by the parent protocol

    @ivar backend: L{IReader} or L{IWriter} provider, that is used for this transfer
    @type backend: L{IReader} or L{IWriter} provider

    """
    supported_options = ('blksize', 'timeout', 'tsize')

    def __init__(self, remote, backend, options=None, _clock=None):
        if options is None:
            self.options = OrderedDict()
        else:
            self.options = options
        self.resultant_options = OrderedDict()
        self.remote = remote
        self.timeout_watchdog = None
        self.backend = backend
        if _clock is not None:
            self._clock = _clock
        else:
            self._clock = reactor

    def processOptions(self, options):
        """Process options mapping, discarding malformed or unknown options.

        @param options: options mapping to process
        @type options: L{OrderedDict<twisted.python.util.OrderedDict>}

        @return: a mapping of processed options. Invalid options are discarded.
        Whether or not the values of options may be changed is decided on a per-
        option basis, according to the standard
        @rtype L{OrderedDict<twisted.python.util.OrderedDict>}

        """
        accepted_options = OrderedDict()
        for name, val in options.iteritems():
            norm_name = name.lower()
            if norm_name in self.supported_options:
                actual_value = getattr(self, 'option_' + norm_name)(val)
                if actual_value is not None:
                    accepted_options[name] = actual_value
        return accepted_options

    def option_blksize(self, val):
        """Process the block size option. Valid range is between 8 and 65464,
        inclusive. If the value is more, than L{MAX_BLOCK_SIZE}, L{MAX_BLOCK_SIZE}
        is returned instead.

        @param val: value of the option
        @type val: C{str}

        @return: accepted option value or C{None}, if it is invalid
        @rtype: C{str} or C{None}

        """
        try:
            int_blksize = int(val)
        except ValueError:
            return None
        if int_blksize < 8 or int_blksize > 65464:
            return None
        int_blksize = min((int_blksize, MAX_BLOCK_SIZE))
        return str(int_blksize)

    def option_timeout(self, val):
        """Process timeout interval option
        (U{RFC2349<http://tools.ietf.org/html/rfc2349>}). Valid range is between 1
        and 255, inclusive.

        @param val: value of the option
        @type val: C{str}

        @return: accepted option value or C{None}, if it is invalid
        @rtype: C{str} or C{None}

        """
        try:
            int_timeout = int(val)
        except ValueError:
            return None
        if int_timeout < 1 or int_timeout > 255:
            return None
        return str(int_timeout)

    def option_tsize(self, val):
        """Process tsize interval option
        (U{RFC2349<http://tools.ietf.org/html/rfc2349>}). Valid range is 0 and up.

        @param val: value of the option
        @type val: C{str}

        @return: accepted option value or C{None}, if it is invalid
        @rtype: C{str} or C{None}

        """
        try:
            int_tsize = int(val)
        except ValueError:
            return None
        if int_tsize < 0:
            return None
        return str(int_tsize)

    def applyOptions(self, session, options):
        """Apply given options mapping to the given L{WriteSession} or
        L{ReadSession} object.

        @param session: A session object to apply the options to
        @type session: L{WriteSession} or L{ReadSession}

        @param options: Options to apply to the session object
        @type options: L{OrderedDict<twisted.python.util.OrderedDict>}

        """
        for opt_name, opt_val in options.iteritems():
            if opt_name == 'blksize':
                session.block_size = int(opt_val)
            elif opt_name == 'timeout':
                timeout = int(opt_val)
                session.timeout = (timeout,) * 3
            elif opt_name == 'tsize':
                tsize = int(opt_val)
                session.tsize = tsize

    def datagramReceived(self, datagram, addr):
        if self.remote[1] != addr[1]:
            self.transport.write(ERRORDatagram.from_code(ERR_TID_UNKNOWN).to_wire())
            return# Does not belong to this transfer
        datagram = TFTPDatagramFactory(*split_opcode(datagram))
        log.msg("Datagram received from %s: %s" % (addr, datagram))
        if datagram.opcode == OP_ERROR:
            return self.tftp_ERROR(datagram)
        return self._datagramReceived(datagram)

    def tftp_ERROR(self, datagram):
        """Handle the L{ERRORDatagram}.

        @param datagram: An ERROR datagram
        @type datagram: L{ERRORDatagram}

        """
        log.msg("Got error: " % datagram)
        return self.cancel()

    def cancel(self):
        """Terminate this protocol instance. If the underlying
        L{ReadSession}/L{WriteSession} is running, delegate the call to it.

        """
        if self.timeout_watchdog is not None and self.timeout_watchdog.active():
            self.timeout_watchdog.cancel()
        if self.session.started:
            self.session.cancel()
        else:
            self.backend.finish()
            self.transport.stopListening()

    def timedOut(self):
        """This protocol instance has timed out during the initial handshake."""
        log.msg("Timed during option negotiation process")
        self.cancel()


class LocalOriginWriteSession(TFTPBootstrap):
    """Bootstraps a L{WriteSession}, that was initiated locally, - we've requested
    a read from a remote server

    """
    def __init__(self, remote, writer, options=None, _clock=None):
        TFTPBootstrap.__init__(self, remote, writer, options, _clock)
        self.session = WriteSession(writer, self._clock)

    def startProtocol(self):
        """Connect the transport and start the L{timeout_watchdog}"""
        self.transport.connect(*self.remote)
        if self.timeout_watchdog is not None:
            self.timeout_watchdog.start()

    def tftp_OACK(self, datagram):
        """Handle the OACK datagram

        @param datagram: OACK datagram
        @type datagram: L{OACKDatagram}

        """
        if not self.session.started:
            self.resultant_options = self.processOptions(datagram.options)
            if self.timeout_watchdog.active():
                self.timeout_watchdog.cancel()
            return self.transport.write(ACKDatagram(0).to_wire())
        else:
            log.msg("Duplicate OACK received, send back ACK and ignore")
            self.transport.write(ACKDatagram(0).to_wire())

    def _datagramReceived(self, datagram):
        if datagram.opcode == OP_OACK:
            return self.tftp_OACK(datagram)
        elif datagram.opcode == OP_DATA and datagram.blocknum == 1:
            if self.timeout_watchdog is not None and self.timeout_watchdog.active():
                self.timeout_watchdog.cancel()
            if not self.session.started:
                self.applyOptions(self.session, self.resultant_options)
                self.session.transport = self.transport
                self.session.startProtocol()
            return self.session.datagramReceived(datagram)
        elif self.session.started:
            return self.session.datagramReceived(datagram)


class RemoteOriginWriteSession(TFTPBootstrap):
    """Bootstraps a L{WriteSession}, that was originated remotely, - we've
    received a WRQ from a client.

    """
    timeout = (1, 3, 7)

    def __init__(self, remote, writer, options=None, _clock=None):
        TFTPBootstrap.__init__(self, remote, writer, options, _clock)
        self.session = WriteSession(writer, self._clock)

    def startProtocol(self):
        """Connect the transport, respond with an initial ACK or OACK (depending on
        if we were initialized with options or not).

        """
        self.transport.connect(*self.remote)
        if self.options:
            self.resultant_options = self.processOptions(self.options)
            bytes = OACKDatagram(self.resultant_options).to_wire()
        else:
            bytes = ACKDatagram(0).to_wire()
        self.timeout_watchdog = SequentialCall.run(
            self.timeout[:-1],
            callable=self.transport.write, callable_args=[bytes, ],
            on_timeout=lambda: self._clock.callLater(self.timeout[-1], self.timedOut),
            run_now=True,
            _clock=self._clock
        )

    def _datagramReceived(self, datagram):
        if datagram.opcode == OP_DATA and datagram.blocknum == 1:
            if self.timeout_watchdog.active():
                self.timeout_watchdog.cancel()
            if not self.session.started:
                self.applyOptions(self.session, self.resultant_options)
                self.session.transport = self.transport
                self.session.startProtocol()
            return self.session.datagramReceived(datagram)
        elif self.session.started:
            return self.session.datagramReceived(datagram)


class LocalOriginReadSession(TFTPBootstrap):
    """Bootstraps a L{ReadSession}, that was originated locally, - we've requested
    a write to a remote server.

    """
    def __init__(self, remote, reader, options=None, _clock=None):
        TFTPBootstrap.__init__(self, remote, reader, options, _clock)
        self.session = ReadSession(reader, self._clock)

    def startProtocol(self):
        """Connect the transport and start the L{timeout_watchdog}"""
        self.transport.connect(*self.remote)
        if self.timeout_watchdog is not None:
            self.timeout_watchdog.start()

    def _datagramReceived(self, datagram):
        if datagram.opcode == OP_OACK:
            return self.tftp_OACK(datagram)
        elif (datagram.opcode == OP_ACK and datagram.blocknum == 0
                    and not self.session.started):
            self.session.transport = self.transport
            self.session.startProtocol()
            if self.timeout_watchdog is not None and self.timeout_watchdog.active():
                self.timeout_watchdog.cancel()
            return self.session.nextBlock()
        elif self.session.started:
            return self.session.datagramReceived(datagram)

    def tftp_OACK(self, datagram):
        """Handle incoming OACK datagram, process and apply options and hand over
        control to the underlying L{ReadSession}.

        @param datagram: OACK datagram
        @type datagram: L{OACKDatagram}

        """
        if not self.session.started:
            self.resultant_options = self.processOptions(datagram.options)
            if self.timeout_watchdog is not None and self.timeout_watchdog.active():
                self.timeout_watchdog.cancel()
            self.applyOptions(self.session, self.resultant_options)
            self.session.transport = self.transport
            self.session.startProtocol()
            return self.session.nextBlock()
        else:
            log.msg("Duplicate OACK received, ignored")

class RemoteOriginReadSession(TFTPBootstrap):
    """Bootstraps a L{ReadSession}, that was started remotely, - we've received
    a RRQ.

    """
    timeout = (1, 3, 7)

    def __init__(self, remote, reader, options=None, _clock=None):
        TFTPBootstrap.__init__(self, remote, reader, options, _clock)
        self.session = ReadSession(reader, self._clock)

    def option_tsize(self, val):
        """Process tsize option.

        If tsize is zero, get the size of the file to be read so that it can
        be returned in the OACK datagram.

        @see: L{TFTPBootstrap.option_tsize}

        """
        val = TFTPBootstrap.option_tsize(self, val)
        if val == str(0):
            val = self.session.reader.size
            if val is not None:
                val = str(val)
        return val

    def startProtocol(self):
        """Start sending an OACK datagram if we were initialized with options
        or start the L{ReadSession} immediately.

        """
        self.transport.connect(*self.remote)
        if self.options:
            self.resultant_options = self.processOptions(self.options)
            bytes = OACKDatagram(self.resultant_options).to_wire()
            self.timeout_watchdog = SequentialCall.run(
                self.timeout[:-1],
                callable=self.transport.write, callable_args=[bytes, ],
                on_timeout=lambda: self._clock.callLater(self.timeout[-1], self.timedOut),
                run_now=True,
                _clock=self._clock
            )
        else:
            self.session.transport = self.transport
            self.session.startProtocol()
            return self.session.nextBlock()

    def _datagramReceived(self, datagram):
        if datagram.opcode == OP_ACK and datagram.blocknum == 0:
            return self.tftp_ACK(datagram)
        elif self.session.started:
            return self.session.datagramReceived(datagram)

    def tftp_ACK(self, datagram):
        """Handle incoming ACK datagram. Hand over control to the underlying
        L{ReadSession}.

        @param datagram: ACK datagram
        @type datagram: L{ACKDatagram}

        """
        if self.timeout_watchdog is not None:
            self.timeout_watchdog.cancel()
        if not self.session.started:
            self.applyOptions(self.session, self.resultant_options)
            self.session.transport = self.transport
            self.session.startProtocol()
            return self.session.nextBlock()
