# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for :class:`FakeMethod`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.fakemethod import (
    FakeMethod,
    MultiFakeMethod,
    )
from maastesting.testcase import TestCase


class TestFakeMethod(TestCase):

    def test_fakemethod_returns_None_by_default(self):
        self.assertEqual(None, FakeMethod()())

    def test_fakemethod_returns_given_value(self):
        self.assertEqual("Input value", FakeMethod("Input value")())

    def test_fakemethod_raises_given_failure(self):
        class ExpectedException(Exception):
            pass

        self.assertRaises(
            ExpectedException,
            FakeMethod(failure=ExpectedException()))

    def test_fakemethod_has_no_calls_initially(self):
        self.assertSequenceEqual([], FakeMethod().calls)

    def test_fakemethod_records_call(self):
        stub = FakeMethod()
        stub()
        self.assertSequenceEqual([((), {})], stub.calls)

    def test_fakemethod_records_args(self):
        stub = FakeMethod()
        stub(1, 2)
        self.assertSequenceEqual([((1, 2), {})], stub.calls)

    def test_fakemethod_records_kwargs(self):
        stub = FakeMethod()
        stub(x=10)
        self.assertSequenceEqual([((), {'x': 10})], stub.calls)

    def test_call_count_is_zero_initially(self):
        self.assertEqual(0, FakeMethod().call_count)

    def test_call_count_counts_calls(self):
        stub = FakeMethod()
        stub()
        self.assertEqual(1, stub.call_count)

    def test_extract_args_returns_just_call_args(self):
        stub = FakeMethod()
        stub(1, 2, 3, x=12)
        self.assertItemsEqual([(1, 2, 3)], stub.extract_args())

    def test_extract_kwargs_returns_just_call_kwargs(self):
        stub = FakeMethod()
        stub(1, 2, 3, x=12)
        self.assertItemsEqual([{'x': 12}], stub.extract_kwargs())


class TestMultiFakeMethod(TestCase):

    def test_call_calls_all_given_methods(self):
        methods = FakeMethod(), FakeMethod()
        method = MultiFakeMethod(methods)
        call1_args = "input 1"
        call2_args = "input 2"
        method(call1_args)
        method(call2_args)
        self.assertEqual(
            [[('input 1',)], [('input 2',)]],
            [methods[0].extract_args(), methods[1].extract_args()])

    def test_raises_if_called_one_time_too_many(self):
        method = MultiFakeMethod([FakeMethod()])
        method()
        self.assertRaises(ValueError, method)
