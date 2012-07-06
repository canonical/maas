'''
@author: shylent
'''
from cStringIO import StringIO
from tftp.netascii import (from_netascii, to_netascii, NetasciiReceiverProxy,
    NetasciiSenderProxy)
from twisted.internet.defer import inlineCallbacks
from twisted.trial import unittest
import re
import tftp


class FromNetascii(unittest.TestCase):

    def setUp(self):
        self._orig_nl = tftp.netascii.NL

    def test_lf_newline(self):
        tftp.netascii.NL = '\x0a'
        self.assertEqual(from_netascii('\x0d\x00'), '\x0d')
        self.assertEqual(from_netascii('\x0d\x0a'), '\x0a')
        self.assertEqual(from_netascii('foo\x0d\x0a\x0abar'), 'foo\x0a\x0abar')
        self.assertEqual(from_netascii('foo\x0d\x0a\x0abar'), 'foo\x0a\x0abar')
        # freestanding CR should not occur, but handle it anyway
        self.assertEqual(from_netascii('foo\x0d\x0a\x0dbar'), 'foo\x0a\x0dbar')

    def test_cr_newline(self):
        tftp.netascii.NL = '\x0d'
        self.assertEqual(from_netascii('\x0d\x00'), '\x0d')
        self.assertEqual(from_netascii('\x0d\x0a'), '\x0d')
        self.assertEqual(from_netascii('foo\x0d\x0a\x0abar'), 'foo\x0d\x0abar')
        self.assertEqual(from_netascii('foo\x0d\x0a\x00bar'), 'foo\x0d\x00bar')
        self.assertEqual(from_netascii('foo\x0d\x00\x0abar'), 'foo\x0d\x0abar')

    def test_crlf_newline(self):
        tftp.netascii.NL = '\x0d\x0a'
        self.assertEqual(from_netascii('\x0d\x00'), '\x0d')
        self.assertEqual(from_netascii('\x0d\x0a'), '\x0d\x0a')
        self.assertEqual(from_netascii('foo\x0d\x00\x0abar'), 'foo\x0d\x0abar')

    def tearDown(self):
        tftp.netascii.NL = self._orig_nl


class ToNetascii(unittest.TestCase):

    def setUp(self):
        self._orig_nl = tftp.netascii.NL
        self._orig_nl_regex = tftp.netascii.re_to_netascii

    def test_lf_newline(self):
        tftp.netascii.NL = '\x0a'
        tftp.netascii.re_to_netascii = re.compile(tftp.netascii._re_to_netascii %
                                                  tftp.netascii.NL)
        self.assertEqual(to_netascii('\x0d'), '\x0d\x00')
        self.assertEqual(to_netascii('\x0a'), '\x0d\x0a')
        self.assertEqual(to_netascii('\x0a\x0d'), '\x0d\x0a\x0d\x00')
        self.assertEqual(to_netascii('\x0d\x0a'), '\x0d\x00\x0d\x0a')

    def test_cr_newline(self):
        tftp.netascii.NL = '\x0d'
        tftp.netascii.re_to_netascii = re.compile(tftp.netascii._re_to_netascii %
                                                  tftp.netascii.NL)
        self.assertEqual(to_netascii('\x0d'), '\x0d\x0a')
        self.assertEqual(to_netascii('\x0a'), '\x0a')
        self.assertEqual(to_netascii('\x0d\x0a'), '\x0d\x0a\x0a')
        self.assertEqual(to_netascii('\x0a\x0d'), '\x0a\x0d\x0a')

    def test_crlf_newline(self):
        tftp.netascii.NL = '\x0d\x0a'
        tftp.netascii.re_to_netascii = re.compile(tftp.netascii._re_to_netascii %
                                                  tftp.netascii.NL)
        self.assertEqual(to_netascii('\x0d\x0a'), '\x0d\x0a')
        self.assertEqual(to_netascii('\x0d'), '\x0d\x00')
        self.assertEqual(to_netascii('\x0d\x0a\x0d'), '\x0d\x0a\x0d\x00')
        self.assertEqual(to_netascii('\x0d\x0d\x0a'), '\x0d\x00\x0d\x0a')

    def tearDown(self):
        tftp.netascii.NL = self._orig_nl
        tftp.netascii.re_to_netascii = self._orig_nl_regex


class ReceiverProxy(unittest.TestCase):

    test_data = """line1
line2
line3
"""
    def setUp(self):
        self.source = StringIO(to_netascii(self.test_data))
        self.sink = StringIO()

    @inlineCallbacks
    def test_conversion(self):
        p = NetasciiReceiverProxy(self.sink)
        chunk = self.source.read(2)
        while chunk:
            yield p.write(chunk)
            chunk = self.source.read(2)
        self.sink.seek(0) # !!!
        self.assertEqual(self.sink.read(), self.test_data)

    @inlineCallbacks
    def test_conversion_byte_by_byte(self):
        p = NetasciiReceiverProxy(self.sink)
        chunk = self.source.read(1)
        while chunk:
            yield p.write(chunk)
            chunk = self.source.read(1)
        self.sink.seek(0) # !!!
        self.assertEqual(self.sink.read(), self.test_data)

    @inlineCallbacks
    def test_conversion_normal(self):
        p = NetasciiReceiverProxy(self.sink)
        chunk = self.source.read(1)
        while chunk:
            yield p.write(chunk)
            chunk = self.source.read(5)
        self.sink.seek(0) # !!!
        self.assertEqual(self.sink.read(), self.test_data)


class SenderProxy(unittest.TestCase):

    test_data = """line1
line2
line3
"""
    def setUp(self):
        self.source = StringIO(self.test_data)
        self.sink = StringIO()

    @inlineCallbacks
    def test_conversion_normal(self):
        p = NetasciiSenderProxy(self.source)
        chunk = yield p.read(5)
        self.assertEqual(len(chunk), 5)
        self.sink.write(chunk)
        last_chunk = False
        while chunk:
            chunk = yield p.read(5)
            # If a terminating chunk (len < blocknum) was already sent, there should
            # be no more data (means, we can only yield empty lines from now on)
            if last_chunk and chunk:
                print "LEN: %s" % len(chunk)
                self.fail("Last chunk (with len < blocksize) was already yielded, "
                          "but there is more data.")
            if len(chunk) < 5:
                last_chunk = True
            self.sink.write(chunk)
        self.sink.seek(0)
        self.assertEqual(self.sink.read(), to_netascii(self.test_data))

    @inlineCallbacks
    def test_conversion_byte_by_byte(self):
        p = NetasciiSenderProxy(self.source)
        chunk = yield p.read(1)
        self.assertEqual(len(chunk), 1)
        self.sink.write(chunk)
        last_chunk = False
        while chunk:
            chunk = yield p.read(1)
            # If a terminating chunk (len < blocknum) was already sent, there should
            # be no more data (means, we can only yield empty lines from now on)
            if last_chunk and chunk:
                print "LEN: %s" % len(chunk)
                self.fail("Last chunk (with len < blocksize) was already yielded, "
                          "but there is more data.")
            if len(chunk) < 1:
                last_chunk = True
            self.sink.write(chunk)
        self.sink.seek(0)
        self.assertEqual(self.sink.read(), to_netascii(self.test_data))

    @inlineCallbacks
    def test_conversion(self):
        p = NetasciiSenderProxy(self.source)
        chunk = yield p.read(2)
        self.assertEqual(len(chunk), 2)
        self.sink.write(chunk)
        last_chunk = False
        while chunk:
            chunk = yield p.read(2)
            # If a terminating chunk (len < blocknum) was already sent, there should
            # be no more data (means, we can only yield empty lines from now on)
            if last_chunk and chunk:
                print "LEN: %s" % len(chunk)
                self.fail("Last chunk (with len < blocksize) was already yielded, "
                          "but there is more data.")
            if len(chunk) < 2:
                last_chunk = True
            self.sink.write(chunk)
        self.sink.seek(0)
        self.assertEqual(self.sink.read(), to_netascii(self.test_data))
