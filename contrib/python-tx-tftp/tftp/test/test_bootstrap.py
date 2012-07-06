'''
@author: shylent
'''
from tftp.bootstrap import (LocalOriginWriteSession, LocalOriginReadSession,
    RemoteOriginReadSession, RemoteOriginWriteSession, TFTPBootstrap)
from tftp.datagram import (ACKDatagram, TFTPDatagramFactory, split_opcode,
    ERR_TID_UNKNOWN, DATADatagram, OACKDatagram)
from tftp.test.test_sessions import DelayedWriter, FakeTransport, DelayedReader
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import Clock
from twisted.python.filepath import FilePath
from twisted.python.util import OrderedDict
from twisted.trial import unittest
import shutil
import tempfile
from tftp.session import MAX_BLOCK_SIZE, WriteSession, ReadSession

ReadSession.timeout = (2, 2, 2)
WriteSession.timeout = (2, 2, 2)
RemoteOriginReadSession.timeout = (2, 2, 2)
RemoteOriginWriteSession.timeout = (2, 2, 2)

class MockHandshakeWatchdog(object):

    def __init__(self, when, f, args=None, kwargs=None, _clock=None):
        self._clock = _clock
        self.when = when
        self.f = f
        self.args = args or []
        self.kwargs = kwargs or {}
        if _clock is None:
            self._clock = reactor
        else:
            self._clock = _clock

    def start(self):
        self.wd = self._clock.callLater(self.when, self.f, *self.args, **self.kwargs)

    def cancel(self):
        if self.wd.active():
            self.wd.cancel()

    def active(self):
        return self.wd.active()

class MockSession(object):
    block_size = 512
    timeout = (1, 3, 5)
    tsize = None

# Testing implementation here, but if I don't, I'll have a TON of duplicate code
class TestOptionProcessing(unittest.TestCase):

    def setUp(self):
        self.proto = TFTPBootstrap(('127.0.0.1', 1111), None)

    def test_empty_options(self):
        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict())
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.block_size, 512)
        self.assertEqual(self.s.timeout, (1, 3, 5))

    def test_blksize(self):
        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'blksize':'8'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.block_size, 8)
        self.assertEqual(opts, OrderedDict({'blksize':'8'}))

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'blksize':'foo'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.block_size, 512)
        self.assertEqual(opts, OrderedDict())

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'blksize':'65464'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.block_size, MAX_BLOCK_SIZE)
        self.assertEqual(opts, OrderedDict({'blksize':str(MAX_BLOCK_SIZE)}))

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'blksize':'65465'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.block_size, 512)
        self.assertEqual(opts, OrderedDict())

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'blksize':'7'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.block_size, 512)
        self.assertEqual(opts, OrderedDict())

    def test_timeout(self):
        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'timeout':'1'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (1, 1, 1))
        self.assertEqual(opts, OrderedDict({'timeout':'1'}))

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'timeout':'foo'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (1, 3, 5))
        self.assertEqual(opts, OrderedDict())

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'timeout':'0'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (1, 3, 5))
        self.assertEqual(opts, OrderedDict())

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'timeout':'255'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (255, 255, 255))
        self.assertEqual(opts, OrderedDict({'timeout':'255'}))

        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'timeout':'256'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (1, 3, 5))
        self.assertEqual(opts, OrderedDict())

    def test_tsize(self):
        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'tsize':'1'}))
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.tsize, 1)
        self.assertEqual(opts, OrderedDict({'tsize':'1'}))

    def test_tsize_ignored_when_not_a_number(self):
        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'tsize':'foo'}))
        self.proto.applyOptions(self.s, opts)
        self.assertIsNone(self.s.tsize)
        self.assertEqual(opts, OrderedDict({}))

    def test_tsize_ignored_when_less_than_zero(self):
        self.s = MockSession()
        opts = self.proto.processOptions(OrderedDict({'tsize':'-1'}))
        self.proto.applyOptions(self.s, opts)
        self.assertIsNone(self.s.tsize)
        self.assertEqual(opts, OrderedDict({}))

    def test_multiple_options(self):
        got_options = OrderedDict()
        got_options['timeout'] = '123'
        got_options['blksize'] = '1024'
        self.s = MockSession()
        opts = self.proto.processOptions(got_options)
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (123, 123, 123))
        self.assertEqual(self.s.block_size, 1024)
        self.assertEqual(opts.items(), got_options.items())

        got_options = OrderedDict()
        got_options['blksize'] = '1024'
        got_options['timeout'] = '123'
        self.s = MockSession()
        opts = self.proto.processOptions(got_options)
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (123, 123, 123))
        self.assertEqual(self.s.block_size, 1024)
        self.assertEqual(opts.items(), got_options.items())

        got_options = OrderedDict()
        got_options['blksize'] = '1024'
        got_options['foobar'] = 'barbaz'
        got_options['timeout'] = '123'
        self.s = MockSession()
        opts = self.proto.processOptions(got_options)
        self.proto.applyOptions(self.s, opts)
        self.assertEqual(self.s.timeout, (123, 123, 123))
        self.assertEqual(self.s.block_size, 1024)
        actual_options = OrderedDict()
        actual_options['blksize'] = '1024'
        actual_options['timeout'] = '123'
        self.assertEqual(opts.items(), actual_options.items())


class BootstrapLocalOriginWrite(unittest.TestCase):

    port = 65466

    def setUp(self):
        self.clock = Clock()
        self.tmp_dir_path = tempfile.mkdtemp()
        self.target = FilePath(self.tmp_dir_path).child('foo')
        self.writer = DelayedWriter(self.target, _clock=self.clock, delay=2)
        self.transport = FakeTransport(hostAddress=('127.0.0.1', self.port))
        self.ws = LocalOriginWriteSession(('127.0.0.1', 65465), self.writer, _clock=self.clock)
        self.wd = MockHandshakeWatchdog(4, self.ws.timedOut, _clock=self.clock)
        self.ws.timeout_watchdog = self.wd
        self.ws.transport = self.transport

    def test_invalid_tid(self):
        self.ws.startProtocol()
        bad_tid_dgram = ACKDatagram(123)
        self.ws.datagramReceived(bad_tid_dgram.to_wire(), ('127.0.0.1', 1111))

        err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assertEqual(err_dgram.errorcode, ERR_TID_UNKNOWN)
        self.addCleanup(self.ws.cancel)
    #test_invalid_tid.skip = 'Will go to another test case'

    def test_local_origin_write_session_handshake_timeout(self):
        self.ws.startProtocol()
        self.clock.advance(5)
        self.failIf(self.transport.value())
        self.failUnless(self.transport.disconnecting)

    def test_local_origin_write_session_handshake_success(self):
        self.ws.session.block_size = 6
        self.ws.startProtocol()
        self.clock.advance(1)
        data_datagram = DATADatagram(1, 'foobar')
        self.ws.datagramReceived(data_datagram.to_wire(), ('127.0.0.1', 65465))
        self.clock.pump((1,)*3)
        self.assertEqual(self.transport.value(), ACKDatagram(1).to_wire())
        self.failIf(self.transport.disconnecting)
        self.failIf(self.wd.active())
        self.addCleanup(self.ws.cancel)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)

class LocalOriginWriteOptionNegotiation(unittest.TestCase):

    port = 65466

    def setUp(self):
        self.clock = Clock()
        self.tmp_dir_path = tempfile.mkdtemp()
        self.target = FilePath(self.tmp_dir_path).child('foo')
        self.writer = DelayedWriter(self.target, _clock=self.clock, delay=2)
        self.transport = FakeTransport(hostAddress=('127.0.0.1', self.port))
        self.ws = LocalOriginWriteSession(('127.0.0.1', 65465), self.writer,
                                          options={'blksize':'123'}, _clock=self.clock)
        self.wd = MockHandshakeWatchdog(4, self.ws.timedOut, _clock=self.clock)
        self.ws.timeout_watchdog = self.wd
        self.ws.transport = self.transport


    def test_option_normal(self):
        self.ws.startProtocol()
        self.ws.datagramReceived(OACKDatagram({'blksize':'12'}).to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(0.1)
        self.assertEqual(self.ws.session.block_size, WriteSession.block_size)
        self.assertEqual(self.transport.value(), ACKDatagram(0).to_wire())

        self.transport.clear()
        self.ws.datagramReceived(OACKDatagram({'blksize':'9'}).to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(0.1)
        self.assertEqual(self.ws.session.block_size, WriteSession.block_size)
        self.assertEqual(self.transport.value(), ACKDatagram(0).to_wire())

        self.transport.clear()
        self.ws.datagramReceived(DATADatagram(1, 'foobarbaz').to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(3)
        self.failUnless(self.ws.session.started)
        self.clock.advance(0.1)
        self.assertEqual(self.ws.session.block_size, 9)
        self.assertEqual(self.transport.value(), ACKDatagram(1).to_wire())

        self.transport.clear()
        self.ws.datagramReceived(DATADatagram(2, 'asdfghjkl').to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(3)
        self.assertEqual(self.transport.value(), ACKDatagram(2).to_wire())
        self.writer.finish()
        self.assertEqual(self.writer.file_path.open('r').read(), 'foobarbazasdfghjkl')

        self.transport.clear()
        self.ws.datagramReceived(OACKDatagram({'blksize':'12'}).to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(0.1)
        self.assertEqual(self.ws.session.block_size, 9)
        self.assertEqual(self.transport.value(), ACKDatagram(0).to_wire())

    def test_option_timeout(self):
        self.ws.startProtocol()
        self.clock.advance(5)
        self.failUnless(self.transport.disconnecting)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)

class BootstrapRemoteOriginWrite(unittest.TestCase):

    port = 65466

    def setUp(self):
        self.clock = Clock()
        self.tmp_dir_path = tempfile.mkdtemp()
        self.target = FilePath(self.tmp_dir_path).child('foo')
        self.writer = DelayedWriter(self.target, _clock=self.clock, delay=2)
        self.transport = FakeTransport(hostAddress=('127.0.0.1', self.port))
        self.ws = RemoteOriginWriteSession(('127.0.0.1', 65465), self.writer, _clock=self.clock)
        self.ws.transport = self.transport
        self.ws.startProtocol()

    @inlineCallbacks
    def test_invalid_tid(self):
        bad_tid_dgram = ACKDatagram(123)
        yield self.ws.datagramReceived(bad_tid_dgram.to_wire(), ('127.0.0.1', 1111))
        err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assertEqual(err_dgram.errorcode, ERR_TID_UNKNOWN)
        self.addCleanup(self.ws.cancel)

    def test_remote_origin_write_bootstrap(self):
        # Initial ACK
        ack_datagram_0 = ACKDatagram(0)
        self.clock.advance(0.1)
        self.assertEqual(self.transport.value(), ack_datagram_0.to_wire())
        self.failIf(self.transport.disconnecting)

        # Normal exchange
        self.transport.clear()
        d = self.ws.datagramReceived(DATADatagram(1, 'foobar').to_wire(), ('127.0.0.1', 65465))
        def cb(res):
            self.clock.advance(0.1)
            ack_datagram_1 = ACKDatagram(1)
            self.assertEqual(self.transport.value(), ack_datagram_1.to_wire())
            self.assertEqual(self.target.open('r').read(), 'foobar')
            self.failIf(self.transport.disconnecting)
            self.addCleanup(self.ws.cancel)
        d.addCallback(cb)
        self.clock.advance(3)
        return d

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)


class RemoteOriginWriteOptionNegotiation(unittest.TestCase):

    port = 65466

    def setUp(self):
        self.clock = Clock()
        self.tmp_dir_path = tempfile.mkdtemp()
        self.target = FilePath(self.tmp_dir_path).child('foo')
        self.writer = DelayedWriter(self.target, _clock=self.clock, delay=2)
        self.transport = FakeTransport(hostAddress=('127.0.0.1', self.port))
        self.options = OrderedDict()
        self.options['blksize'] = '9'
        self.options['tsize'] = '45'
        self.ws = RemoteOriginWriteSession(
            ('127.0.0.1', 65465), self.writer, options=self.options,
            _clock=self.clock)
        self.ws.transport = self.transport

    def test_option_normal(self):
        self.ws.startProtocol()
        self.clock.advance(0.1)
        oack_datagram = OACKDatagram(self.options).to_wire()
        self.assertEqual(self.transport.value(), oack_datagram)
        self.clock.advance(3)
        self.assertEqual(self.transport.value(), oack_datagram * 2)

        self.transport.clear()
        self.ws.datagramReceived(DATADatagram(1, 'foobarbaz').to_wire(), ('127.0.0.1', 65465))
        self.clock.pump((1,)*3)
        self.assertEqual(self.transport.value(), ACKDatagram(1).to_wire())
        self.assertEqual(self.ws.session.block_size, 9)

        self.transport.clear()
        self.ws.datagramReceived(DATADatagram(2, 'smthng').to_wire(), ('127.0.0.1', 65465))
        self.clock.pump((1,)*3)
        self.assertEqual(self.transport.value(), ACKDatagram(2).to_wire())
        self.clock.pump((1,)*10)
        self.writer.finish()
        self.assertEqual(self.writer.file_path.open('r').read(), 'foobarbazsmthng')
        self.failUnless(self.transport.disconnecting)

    def test_option_timeout(self):
        self.ws.startProtocol()
        self.clock.advance(0.1)
        oack_datagram = OACKDatagram(self.options).to_wire()
        self.assertEqual(self.transport.value(), oack_datagram)
        self.failIf(self.transport.disconnecting)

        self.clock.advance(3)
        self.assertEqual(self.transport.value(), oack_datagram * 2)
        self.failIf(self.transport.disconnecting)

        self.clock.advance(2)
        self.assertEqual(self.transport.value(), oack_datagram * 3)
        self.failIf(self.transport.disconnecting)

        self.clock.advance(2)
        self.assertEqual(self.transport.value(), oack_datagram * 3)
        self.failUnless(self.transport.disconnecting)

    def test_option_tsize(self):
        # A tsize option sent as part of a write session is recorded.
        self.ws.startProtocol()
        self.clock.advance(0.1)
        oack_datagram = OACKDatagram(self.options).to_wire()
        self.assertEqual(self.transport.value(), oack_datagram)
        self.failIf(self.transport.disconnecting)
        self.assertIsInstance(self.ws.session, WriteSession)
        # Options are not applied to the WriteSession until the first DATA
        # datagram is received,
        self.assertIsNone(self.ws.session.tsize)
        self.ws.datagramReceived(
            DATADatagram(1, 'foobarbaz').to_wire(), ('127.0.0.1', 65465))
        # The tsize option has been applied to the WriteSession.
        self.assertEqual(45, self.ws.session.tsize)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)


class BootstrapLocalOriginRead(unittest.TestCase):
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
        self.rs = LocalOriginReadSession(('127.0.0.1', 65465), self.reader, _clock=self.clock)
        self.wd = MockHandshakeWatchdog(4, self.rs.timedOut, _clock=self.clock)
        self.rs.timeout_watchdog = self.wd
        self.rs.transport = self.transport
        self.rs.startProtocol()

    def test_invalid_tid(self):
        data_datagram = DATADatagram(1, 'foobar')
        self.rs.datagramReceived(data_datagram, ('127.0.0.1', 11111))
        self.clock.advance(0.1)
        err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assertEqual(err_dgram.errorcode, ERR_TID_UNKNOWN)
        self.addCleanup(self.rs.cancel)

    def test_local_origin_read_session_handshake_timeout(self):
        self.clock.advance(5)
        self.failIf(self.transport.value())
        self.failUnless(self.transport.disconnecting)

    def test_local_origin_read_session_handshake_success(self):
        self.clock.advance(1)
        ack_datagram = ACKDatagram(0)
        self.rs.datagramReceived(ack_datagram.to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(2)
        self.failUnless(self.transport.value())
        self.failIf(self.transport.disconnecting)
        self.failIf(self.wd.active())
        self.addCleanup(self.rs.cancel)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)


class LocalOriginReadOptionNegotiation(unittest.TestCase):
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
        self.rs = LocalOriginReadSession(('127.0.0.1', 65465), self.reader, _clock=self.clock)
        self.wd = MockHandshakeWatchdog(4, self.rs.timedOut, _clock=self.clock)
        self.rs.timeout_watchdog = self.wd
        self.rs.transport = self.transport

    def test_option_normal(self):
        self.rs.startProtocol()
        self.rs.datagramReceived(OACKDatagram({'blksize':'9'}).to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(0.1)
        self.assertEqual(self.rs.session.block_size, 9)
        self.clock.pump((1,)*3)
        self.assertEqual(self.transport.value(), DATADatagram(1, self.test_data[:9]).to_wire())

        self.rs.datagramReceived(OACKDatagram({'blksize':'12'}).to_wire(), ('127.0.0.1', 65465))
        self.clock.advance(0.1)
        self.assertEqual(self.rs.session.block_size, 9)

        self.transport.clear()
        self.rs.datagramReceived(ACKDatagram(1).to_wire(), ('127.0.0.1', 65465))
        self.clock.pump((1,)*3)
        self.assertEqual(self.transport.value(), DATADatagram(2, self.test_data[9:18]).to_wire())

        self.addCleanup(self.rs.cancel)

    def test_local_origin_read_option_timeout(self):
        self.rs.startProtocol()
        self.clock.advance(5)
        self.failUnless(self.transport.disconnecting)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)


class BootstrapRemoteOriginRead(unittest.TestCase):
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
        self.rs = RemoteOriginReadSession(('127.0.0.1', 65465), self.reader, _clock=self.clock)
        self.rs.transport = self.transport

    @inlineCallbacks
    def test_invalid_tid(self):
        self.rs.startProtocol()
        data_datagram = DATADatagram(1, 'foobar')
        yield self.rs.datagramReceived(data_datagram, ('127.0.0.1', 11111))
        err_dgram = TFTPDatagramFactory(*split_opcode(self.transport.value()))
        self.assertEqual(err_dgram.errorcode, ERR_TID_UNKNOWN)
        self.addCleanup(self.rs.cancel)

    def test_remote_origin_read_bootstrap(self):
        # First datagram
        self.rs.session.block_size = 5
        self.rs.startProtocol()
        self.clock.pump((1,)*3)

        data_datagram_1 = DATADatagram(1, self.test_data[:5])

        self.assertEqual(self.transport.value(), data_datagram_1.to_wire())
        self.failIf(self.transport.disconnecting)

        # Normal exchange continues
        self.transport.clear()
        self.rs.datagramReceived(ACKDatagram(1).to_wire(), ('127.0.0.1', 65465))
        self.clock.pump((1,)*3)
        data_datagram_2 = DATADatagram(2, self.test_data[5:10])
        self.assertEqual(self.transport.value(), data_datagram_2.to_wire())
        self.failIf(self.transport.disconnecting)
        self.addCleanup(self.rs.cancel)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)


class RemoteOriginReadOptionNegotiation(unittest.TestCase):
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
        self.options = OrderedDict()
        self.options['blksize'] = '9'
        self.options['tsize'] = '34'
        self.rs = RemoteOriginReadSession(('127.0.0.1', 65465), self.reader,
                                          options=self.options, _clock=self.clock)
        self.rs.transport = self.transport

    def test_option_normal(self):
        self.rs.startProtocol()
        self.clock.advance(0.1)
        oack_datagram = OACKDatagram(self.options).to_wire()
        self.assertEqual(self.transport.value(), oack_datagram)
        self.clock.advance(3)
        self.assertEqual(self.transport.value(), oack_datagram * 2)

        self.transport.clear()
        self.rs.datagramReceived(ACKDatagram(0).to_wire(), ('127.0.0.1', 65465))
        self.clock.pump((1,)*3)
        self.assertEqual(self.transport.value(), DATADatagram(1, self.test_data[:9]).to_wire())

        self.addCleanup(self.rs.cancel)

    def test_option_timeout(self):
        self.rs.startProtocol()
        self.clock.advance(0.1)
        oack_datagram = OACKDatagram(self.options).to_wire()
        self.assertEqual(self.transport.value(), oack_datagram)
        self.failIf(self.transport.disconnecting)

        self.clock.advance(3)
        self.assertEqual(self.transport.value(), oack_datagram * 2)
        self.failIf(self.transport.disconnecting)

        self.clock.advance(2)
        self.assertEqual(self.transport.value(), oack_datagram * 3)
        self.failIf(self.transport.disconnecting)

        self.clock.advance(2)
        self.assertEqual(self.transport.value(), oack_datagram * 3)
        self.failUnless(self.transport.disconnecting)

    def test_option_tsize(self):
        # A tsize option of 0 sent as part of a read session prompts a tsize
        # response with the actual size of the file.
        self.options['tsize'] = '0'
        self.rs.startProtocol()
        self.clock.advance(0.1)
        self.transport.clear()
        self.clock.advance(3)
        # The response contains the size of the test data.
        self.options['tsize'] = str(len(self.test_data))
        oack_datagram = OACKDatagram(self.options).to_wire()
        self.assertEqual(self.transport.value(), oack_datagram)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir_path)
