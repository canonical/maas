'''
@author: shylent
'''
from tftp.util import SequentialCall, Spent, Cancelled
from twisted.internet.task import Clock
from twisted.trial import unittest


class CallCounter(object):
    call_num = 0

    def __call__(self):
        self.call_num += 1


class SequentialCalling(unittest.TestCase):

    def setUp(self):
        self.f = CallCounter()
        self.t = CallCounter()
        self.clock = Clock()

    def test_empty(self):
        SequentialCall.run((), self.f, on_timeout=self.t, _clock=self.clock)
        self.clock.pump((1,))
        self.assertEqual(self.f.call_num, 0)
        self.assertEqual(self.t.call_num, 1)

    def test_empty_now(self):
        SequentialCall.run((), self.f, on_timeout=self.t, run_now=True, _clock=self.clock)
        self.clock.pump((1,))
        self.assertEqual(self.f.call_num, 1)
        self.assertEqual(self.t.call_num, 1)

    def test_non_empty(self):
        c = SequentialCall.run((1, 3, 5), self.f, run_now=True, on_timeout=self.t, _clock=self.clock)
        self.clock.advance(0.1)
        self.failUnless(c.active())
        self.assertEqual(self.f.call_num, 1)
        self.clock.pump((1,)*2)
        self.failUnless(c.active())
        self.assertEqual(self.f.call_num, 2)
        self.clock.pump((1,)*3)
        self.failUnless(c.active())
        self.assertEqual(self.f.call_num, 3)
        self.clock.pump((1,)*5)
        self.failIf(c.active())
        self.assertEqual(self.f.call_num, 4)
        self.assertEqual(self.t.call_num, 1)
        self.assertRaises(Spent, c.reschedule)
        self.assertRaises(Spent, c.cancel)

    def test_cancel(self):
        c = SequentialCall.run((1, 3, 5), self.f, on_timeout=self.t, _clock=self.clock)
        self.clock.pump((1,)*2)
        self.assertEqual(self.f.call_num, 1)
        c.cancel()
        self.assertRaises(Cancelled, c.cancel)
        self.assertEqual(self.t.call_num, 0)
        self.assertRaises(Cancelled, c.reschedule)

    def test_cancel_immediately(self):
        c = SequentialCall.run((1, 3, 5), lambda: c.cancel(), run_now=True,
                               on_timeout=self.t, _clock=self.clock)
        self.clock.pump((1,)*2)
        self.assertRaises(Cancelled, c.cancel)
        self.assertEqual(self.t.call_num, 0)
        self.assertRaises(Cancelled, c.reschedule)
