'''
@author: shylent
'''
from tftp.datagram import (split_opcode, WireProtocolError, TFTPDatagramFactory,
    RQDatagram, DATADatagram, ACKDatagram, ERRORDatagram, errors, OP_RRQ, OP_WRQ,
    OACKDatagram)
from tftp.errors import OptionsDecodeError
from twisted.trial import unittest


class OpcodeProcessing(unittest.TestCase):

    def test_zero_length(self):
        self.assertRaises(WireProtocolError, split_opcode, '')

    def test_incomplete_opcode(self):
        self.assertRaises(WireProtocolError, split_opcode, '0')

    def test_empty_payload(self):
        self.assertEqual(split_opcode('\x00\x01'), (1, ''))

    def test_non_empty_payload(self):
        self.assertEqual(split_opcode('\x00\x01foo'), (1, 'foo'))

    def test_unknown_opcode(self):
        opcode = 17
        self.assertRaises(WireProtocolError, TFTPDatagramFactory, opcode, 'foobar')


class ConcreteDatagrams(unittest.TestCase):

    def test_rq(self):
        # Only one field - not ok
        self.assertRaises(WireProtocolError, RQDatagram.from_wire, 'foobar')
        # Two fields - ok (unterminated, slight deviation from the spec)
        dgram = RQDatagram.from_wire('foo\x00bar')
        dgram.opcode = OP_RRQ
        self.assertEqual(dgram.to_wire(), '\x00\x01foo\x00bar\x00')
        # Two fields terminated is ok too
        RQDatagram.from_wire('foo\x00bar\x00')
        dgram.opcode = OP_RRQ
        self.assertEqual(dgram.to_wire(), '\x00\x01foo\x00bar\x00')
        # More than two fields is also ok (unterminated, slight deviation from the spec)
        dgram = RQDatagram.from_wire('foo\x00bar\x00baz\x00spam')
        self.assertEqual(dgram.options, {'baz':'spam'})
        dgram.opcode = OP_WRQ
        self.assertEqual(dgram.to_wire(), '\x00\x02foo\x00bar\x00baz\x00spam\x00')
        # More than two fields is also ok (terminated)
        dgram = RQDatagram.from_wire('foo\x00bar\x00baz\x00spam\x00one\x00two\x00')
        self.assertEqual(dgram.options, {'baz':'spam', 'one':'two'})
        dgram.opcode = OP_RRQ
        self.assertEqual(dgram.to_wire(),
            '\x00\x01foo\x00bar\x00baz\x00spam\x00one\x00two\x00')
        # Option with no value - not ok
        self.assertRaises(OptionsDecodeError,
            RQDatagram.from_wire, 'foo\x00bar\x00baz\x00spam\x00one\x00')
        # Duplicate option - not ok
        self.assertRaises(OptionsDecodeError,
            RQDatagram.from_wire,
            'foo\x00bar\x00baz\x00spam\x00one\x00two\x00baz\x00val\x00')

    def test_rrq(self):
        self.assertEqual(TFTPDatagramFactory(*split_opcode('\x00\x01foo\x00bar')).to_wire(),
                         '\x00\x01foo\x00bar\x00')

    def test_wrq(self):
        self.assertEqual(TFTPDatagramFactory(*split_opcode('\x00\x02foo\x00bar')).to_wire(),
                         '\x00\x02foo\x00bar\x00')

    def test_oack(self):
        # Zero options (I don't know if it is ok, the standard doesn't say anything)
        dgram = OACKDatagram.from_wire('')
        self.assertEqual(dgram.to_wire(), '\x00\x06')
        # One option, terminated
        dgram = OACKDatagram.from_wire('foo\x00bar\x00')
        self.assertEqual(dgram.options, {'foo':'bar'})
        self.assertEqual(dgram.to_wire(), '\x00\x06foo\x00bar\x00')
        # Not terminated
        dgram = OACKDatagram.from_wire('foo\x00bar\x00baz\x00spam')
        self.assertEqual(dgram.options, {'foo':'bar', 'baz':'spam'})
        self.assertEqual(dgram.to_wire(), '\x00\x06foo\x00bar\x00baz\x00spam\x00')
        # Option with no value
        self.assertRaises(OptionsDecodeError, OACKDatagram.from_wire,
            'foo\x00bar\x00baz')
        # Duplicate option
        self.assertRaises(OptionsDecodeError,
            OACKDatagram.from_wire,
            'baz\x00spam\x00one\x00two\x00baz\x00val\x00')

    def test_data(self):
        # Zero-length payload
        self.assertRaises(WireProtocolError, DATADatagram.from_wire, '')
        # One byte payload
        self.assertRaises(WireProtocolError, DATADatagram.from_wire, '\x00')
        # Zero-length data
        self.assertEqual(DATADatagram.from_wire('\x00\x01').to_wire(),
                         '\x00\x03\x00\x01')
        # Full-length data
        self.assertEqual(DATADatagram.from_wire('\x00\x01foobar').to_wire(),
                         '\x00\x03\x00\x01foobar')

    def test_ack(self):
        # Zero-length payload
        self.assertRaises(WireProtocolError, ACKDatagram.from_wire, '')
        # One byte payload
        self.assertRaises(WireProtocolError, ACKDatagram.from_wire, '\x00')
        # Full-length payload
        self.assertEqual(ACKDatagram.from_wire('\x00\x0a').blocknum, 10)
        self.assertEqual(ACKDatagram.from_wire('\x00\x0a').to_wire(), '\x00\x04\x00\x0a')
        # Extra data in payload
        self.assertRaises(WireProtocolError, ACKDatagram.from_wire, '\x00\x10foobarz')

    def test_error(self):
        # Zero-length payload
        self.assertRaises(WireProtocolError, ERRORDatagram.from_wire, '')
        # One byte payload
        self.assertRaises(WireProtocolError, ERRORDatagram.from_wire, '\x00')
        # Errorcode only (maybe this should fail)
        dgram = ERRORDatagram.from_wire('\x00\x01')
        self.assertEqual(dgram.errorcode, 1)
        self.assertEqual(dgram.errmsg, errors[1])
        # Errorcode with errstring - not terminated
        dgram = ERRORDatagram.from_wire('\x00\x01foobar')
        self.assertEqual(dgram.errorcode, 1)
        self.assertEqual(dgram.errmsg, 'foobar')
        # Errorcode with errstring - terminated
        dgram = ERRORDatagram.from_wire('\x00\x01foobar\x00')
        self.assertEqual(dgram.errorcode, 1)
        self.assertEqual(dgram.errmsg, 'foobar')
        # Unknown errorcode
        self.assertRaises(WireProtocolError, ERRORDatagram.from_wire, '\x00\x0efoobar')
        # Unknown errorcode in from_code
        self.assertRaises(WireProtocolError, ERRORDatagram.from_code, 13)
        # from_code with custom message
        dgram = ERRORDatagram.from_code(3, "I've accidentally the whole message")
        self.assertEqual(dgram.errorcode, 3)
        self.assertEqual(dgram.errmsg, "I've accidentally the whole message")
        self.assertEqual(dgram.to_wire(), "\x00\x05\x00\x03I've accidentally the whole message\x00")
        # from_code default message
        dgram = ERRORDatagram.from_code(3)
        self.assertEqual(dgram.errorcode, 3)
        self.assertEqual(dgram.errmsg, "Disk full or allocation exceeded")
        self.assertEqual(dgram.to_wire(), "\x00\x05\x00\x03Disk full or allocation exceeded\x00")
