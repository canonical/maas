'''
@author: shylent
'''
from tftp.backend import FilesystemWriter, FilesystemReader, IReader, IWriter
from tftp.datagram import (ACKDatagram, ERRORDatagram,
    ERR_NOT_DEFINED, DATADatagram, TFTPDatagramFactory, split_opcode)
from tftp.session import WriteSession, ReadSession
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.task import Clock
from twisted.python.filepath import FilePath
from twisted.test.proto_helpers import StringTransport
from twisted.trial import unittest
from zope import interface
import shutil
import tempfile

ReadSession.timeout = (2, 2, 2)
WriteSession.timeout = (2, 2, 2)

class DelayedReader(FilesystemReader):

    def __init__(self, *args, **kwargs):
        self.delay = kwargs.pop('delay')
        self._clock = kwargs.pop('_clock', reactor)
        FilesystemReader.__init__(self, *args, **kwargs)

    def read(self, size):
        data = FilesystemReader.read(self, size)
        d = Deferred()
        def c(ign):
            return data
        d.addCallback(c)
        self._clock.callLater(self.delay, d.callback, None)
        return d


class DelayedWriter(FilesystemWriter):

    def __init__(self, *args, **kwargs):
        self.delay = kwargs.pop('delay')
        self._clock = kwargs.pop('_clock', reactor)
        FilesystemWriter.__init__(self, *args, **kwargs)

    def write(self, data):
        d = Deferred()
        def c(ign):
            return FilesystemWriter.write(self, data)
        d.addCallback(c)
        self._clock.callLater(self.delay, d.callback, None)
        return d


class FailingReader(object):
    interface.implements(IReader)

    size = None

    def read(self, size):
        raise IOError('A failure')

    def finish(self):
        pass


class FailingWriter(object):
    interface.implements(IWriter)

    def write(self, data):
        raise IOError("I fail")

    def cancel(self):
        pass

    def finish(self):
        pass


class FakeTransport(StringTransport):
    stopListening = StringTransport.loseConnection

    def connect(self, host, port):
        self._connectedAddr = (host, port)


class WriteSessions(unittest.TestCase):

    port = 65466

    def setUp(self):
        self.clock = Clock()
        self.tmp_dir_path = tempfile.mkdtemp()
        self.target = FilePath(self.tmp_dir_path).child('foo')
        self.writer = DelayedWriter(self.target, _clock=self.clock, delay=2)
        self.transport = FakeTransport(hostAddress=('127.0.0.1', self.port))
        self.ws = WriteSession(self.writer, _clock=self.clock)
        self.ws.timeout = (4, 4, 4)
        self.ws.transport = self.transport
        self.ws.startProtocol()

    def test_ERROR(self):
        err_dgram = ERRORDatagram.from_code(ERR_NOT_DEFINED, 'no reason')
        self.ws.datagramReceived(err_dgram)
        self.clock.advance(0.1)
        self.failIf(self.transport.value())
        self.failUnless(self.transport.disconnecting)

    @inlineCallbacks
    def test_DATA_stale_blocknum(self):
        self.ws.block_size = 6
        self.ws.blocknum = 2
        data_datagram = DATADatagram(1, 'foobar')
        yield self.ws.datagramReceived(data_datagram)
        self.writer.finish()
        self.failIf(self.target.open('r').read())
        self.failIf(self.transport.disconnecting)
        ack_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assertEqual(ack_dgram.blocknum, 1)
        self.addCleanup(self.ws.cancel)

    @inlineCallbacks
    def test_DATA_invalid_blocknum(self):
        self.ws.block_size = 6
        data_datagram = DATADatagram(3, 'foobar')
        yield self.ws.datagramReceived(data_datagram)
        self.writer.finish()
        self.failIf(self.target.open('r').read())
        self.failIf(self.transport.disconnecting)
        err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assert_(isinstance(err_dgram, ERRORDatagram))
        self.addCleanup(self.ws.cancel)

    def test_DATA(self):
        self.ws.block_size = 6
        data_datagram = DATADatagram(1, 'foobar')
        d = self.ws.datagramReceived(data_datagram)
        def cb(ign):
            self.clock.advance(0.1)
            #self.writer.finish()
            #self.assertEqual(self.target.open('r').read(), 'foobar')
            self.failIf(self.transport.disconnecting)
            ack_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
            self.assertEqual(ack_dgram.blocknum, 1)
            self.failIf(self.ws.completed,
                        "Data length is equal to blocksize, no reason to stop")
            data_datagram = DATADatagram(2, 'barbaz')

            self.transport.clear()
            d = self.ws.datagramReceived(data_datagram)
            d.addCallback(cb_)
            self.clock.advance(3)
            return d
        def cb_(ign):
            self.clock.advance(0.1)
            self.failIf(self.transport.disconnecting)
            ack_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
            self.assertEqual(ack_dgram.blocknum, 2)
            self.failIf(self.ws.completed,
                        "Data length is equal to blocksize, no reason to stop")
        d.addCallback(cb)
        self.addCleanup(self.ws.cancel)
        self.clock.advance(3)
        return d

    def test_DATA_finished(self):
        self.ws.block_size = 6

        # Send a terminating datagram
        data_datagram = DATADatagram(1, 'foo')
        d = self.ws.datagramReceived(data_datagram)
        def cb(res):
            self.clock.advance(0.1)
            self.assertEqual(self.target.open('r').read(), 'foo')
            ack_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
            self.failUnless(isinstance(ack_dgram, ACKDatagram))
            self.failUnless(self.ws.completed,
                        "Data length is less, than blocksize, time to stop")
            self.transport.clear()

            # Send another datagram after the transfer is considered complete
            data_datagram = DATADatagram(2, 'foobar')
            self.ws.datagramReceived(data_datagram)
            self.assertEqual(self.target.open('r').read(), 'foo')
            err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
            self.failUnless(isinstance(err_dgram, ERRORDatagram))

            # Check for proper disconnection after grace timeout expires
            self.clock.pump((4,)*4)
            self.failUnless(self.transport.disconnecting,
                "We are done and the grace timeout is over, should disconnect")
        d.addCallback(cb)
        self.clock.advance(2)
        return d

    def test_DATA_backoff(self):
        self.ws.block_size = 5

        data_datagram = DATADatagram(1, 'foobar')
        d = self.ws.datagramReceived(data_datagram)
        def cb(ign):
            self.clock.advance(0.1)
            ack_datagram = ACKDatagram(1)

            self.clock.pump((1,)*5)
            # Sent two times - initial send and a retransmit after first timeout
            self.assertEqual(self.transport.value(),
                             ack_datagram.to_wire()*2)

            # Sent three times - initial send and two retransmits
            self.clock.pump((1,)*4)
            self.assertEqual(self.transport.value(),
                             ack_datagram.to_wire()*3)

            # Sent still three times - initial send, two retransmits and the last wait
            self.clock.pump((1,)*4)
            self.assertEqual(self.transport.value(),
                             ack_datagram.to_wire()*3)

            self.failUnless(self.transport.disconnecting)
        d.addCallback(cb)
        self.clock.advance(2.1)
        return d

    @inlineCallbacks
    def test_failed_write(self):
        self.writer.cancel()
        self.ws.writer = FailingWriter()
        data_datagram = DATADatagram(1, 'foobar')
        yield self.ws.datagramReceived(data_datagram)
        self.flushLoggedErrors()
        self.clock.advance(0.1)
        err_datagram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.failUnless(isinstance(err_datagram, ERRORDatagram))
        self.failUnless(self.transport.disconnecting)

    def test_time_out(self):
        data_datagram = DATADatagram(1, 'foobar')
        d = self.ws.datagramReceived(data_datagram)
        def cb(ign):
            self.clock.pump((1,)*13)
            self.failUnless(self.transport.disconnecting)
        d.addCallback(cb)
        self.clock.advance(4)
        return d

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)


class ReadSessions(unittest.TestCase):
    test_data = """line1
line2
anotherline"""
    port = 65466

    def setUp(self):
        self.clock = Clock()
        self.tmp_dir_path = tempfile.mkdtemp()
        self.target = FilePath(self.tmp_dir_path).child('foo')
        with self.target.open('wb') as temp_fd:
            temp_fd.write(self.test_data)
        self.reader = DelayedReader(self.target, _clock=self.clock, delay=2)
        self.transport = FakeTransport(hostAddress=('127.0.0.1', self.port))
        self.rs = ReadSession(self.reader, _clock=self.clock)
        self.rs.transport = self.transport
        self.rs.startProtocol()

    @inlineCallbacks
    def test_ERROR(self):
        err_dgram = ERRORDatagram.from_code(ERR_NOT_DEFINED, 'no reason')
        yield self.rs.datagramReceived(err_dgram)
        self.failIf(self.transport.value())
        self.failUnless(self.transport.disconnecting)

    @inlineCallbacks
    def test_ACK_invalid_blocknum(self):
        ack_datagram = ACKDatagram(3)
        yield self.rs.datagramReceived(ack_datagram)
        self.failIf(self.transport.disconnecting)
        err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assert_(isinstance(err_dgram, ERRORDatagram))
        self.addCleanup(self.rs.cancel)

    @inlineCallbacks
    def test_ACK_stale_blocknum(self):
        self.rs.blocknum = 2
        ack_datagram = ACKDatagram(1)
        yield self.rs.datagramReceived(ack_datagram)
        self.failIf(self.transport.disconnecting)
        self.failIf(self.transport.value(),
                    "Stale ACK datagram, we should not write anything back")
        self.addCleanup(self.rs.cancel)

    def test_ACK(self):
        self.rs.block_size = 5
        self.rs.blocknum = 1
        ack_datagram = ACKDatagram(1)
        d = self.rs.datagramReceived(ack_datagram)
        def cb(ign):
            self.clock.advance(0.1)
            self.failIf(self.transport.disconnecting)
            data_datagram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
            self.assertEqual(data_datagram.data, 'line1')
            self.failIf(self.rs.completed,
                        "Got enough bytes from the reader, there is no reason to stop")
        d.addCallback(cb)
        self.clock.advance(2.5)
        self.addCleanup(self.rs.cancel)
        return d

    def test_ACK_finished(self):
        self.rs.block_size = 512
        self.rs.blocknum = 1

        # Send a terminating datagram
        ack_datagram = ACKDatagram(1)
        d = self.rs.datagramReceived(ack_datagram)
        def cb(ign):
            self.clock.advance(0.1)
            ack_datagram = ACKDatagram(2)
            # This datagram doesn't trigger any sends
            self.rs.datagramReceived(ack_datagram)

            self.assertEqual(self.transport.value(), DATADatagram(2, self.test_data).to_wire())
            self.failUnless(self.rs.completed,
                        "Data length is less, than blocksize, time to stop")
        self.addCleanup(self.rs.cancel)
        d.addCallback(cb)
        self.clock.advance(3)
        return d

    def test_ACK_backoff(self):
        self.rs.block_size = 5
        self.rs.blocknum = 1

        ack_datagram = ACKDatagram(1)
        d = self.rs.datagramReceived(ack_datagram)
        def cb(ign):

            self.clock.pump((1,)*4)
            # Sent two times - initial send and a retransmit after first timeout
            self.assertEqual(self.transport.value(),
                             DATADatagram(2, self.test_data[:5]).to_wire()*2)

            # Sent three times - initial send and two retransmits
            self.clock.pump((1,)*5)
            self.assertEqual(self.transport.value(),
                             DATADatagram(2, self.test_data[:5]).to_wire()*3)

            # Sent still three times - initial send, two retransmits and the last wait
            self.clock.pump((1,)*10)
            self.assertEqual(self.transport.value(),
                             DATADatagram(2, self.test_data[:5]).to_wire()*3)

            self.failUnless(self.transport.disconnecting)
        d.addCallback(cb)
        self.clock.advance(2.5)
        return d

    @inlineCallbacks
    def test_failed_read(self):
        self.reader.finish()
        self.rs.reader = FailingReader()
        self.rs.blocknum = 1
        ack_datagram = ACKDatagram(1)
        yield self.rs.datagramReceived(ack_datagram)
        self.flushLoggedErrors()
        self.clock.advance(0.1)
        err_datagram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.failUnless(isinstance(err_datagram, ERRORDatagram))
        self.failUnless(self.transport.disconnecting)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)
