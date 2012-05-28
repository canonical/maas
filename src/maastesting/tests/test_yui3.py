# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.testing.yui3`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.testcase import TestCase
from maastesting.yui3 import (
    extract_tests,
    gen_failed_test_messages,
    get_failed_tests_message,
    )
from nose.tools import nottest

# Nose is over-zealous.
nottest(extract_tests)
nottest(gen_failed_test_messages)
nottest(get_failed_tests_message)


# From http://yuilibrary.com/yui/docs/test/#testsuite-level-events
example_results = {
    'failed': 3,
    'ignored': 0,
    'name': 'Test Suite 0',
    'passed': 3,
    'testCase0': {
        'failed': 1,
        'ignored': 0,
        'name': 'testCase0',
        'passed': 1,
        'test0': {
            'message': 'Test passed.',
            'name': 'test0',
            'result': 'pass',
            'type': 'test',
            },
        'test1': {
            'message': 'Assertion failed.',
            'name': 'test1',
            'result': 'fail',
            'type': 'test',
            },
        'total': 2,
        'type': 'testcase',
        },
    'testCase1': {
        'failed': 1,
        'ignored': 0,
        'name': 'testCase1',
        'passed': 1,
        'test0': {
            'message': 'Test passed.',
            'name': 'test0',
            'result': 'pass',
            'type': 'test',
            },
        'test1': {
            'message': 'Assertion failed.',
            'name': 'test1',
            'result': 'fail',
            'type': 'test',
            },
        'total': 2,
        'type': 'testcase',
        },
    'testSuite0': {
        'failed': 1,
        'ignored': 0,
        'name': 'testSuite0',
        'passed': 1,
        'testCase2': {
            'failed': 1,
            'ignored': 0,
            'name': 'testCase2',
            'passed': 1,
            'test0': {
                'message': 'Test passed.',
                'name': 'test0',
                'result': 'pass',
                'type': 'test',
                },
            'test1': {
                'message': 'Assertion failed.',
                'name': 'test1',
                'result': 'fail',
                'type': 'test',
                },
            'total': 2,
            'type': 'testcase'},
        'total': 2,
        'type': 'testsuite'},
    'total': 6,
    'type': 'testsuite',
    }


class TestFunctions(TestCase):

    def test_extract_tests_names(self):
        expected_names = {
            "testCase0.test0",
            "testCase0.test1",
            "testCase1.test0",
            "testCase1.test1",
            "testSuite0.testCase2.test0",
            "testSuite0.testCase2.test1",
            }
        observed_tests = extract_tests(example_results)
        observed_test_names = set(observed_tests)
        self.assertSetEqual(expected_names, observed_test_names)

    def test_extract_tests(self):
        expected_results = {
            "testCase0.test0": "pass",
            "testCase0.test1": "fail",
            "testCase1.test0": "pass",
            "testCase1.test1": "fail",
            "testSuite0.testCase2.test0": "pass",
            "testSuite0.testCase2.test1": "fail",
            }
        observed_results = {
            name: test["result"]
            for name, test in extract_tests(example_results).items()
            }
        self.assertDictEqual(expected_results, observed_results)

    def test_gen_failed_test_messages(self):
        expected_messages = {
            "testCase0.test1: Assertion failed.",
            "testCase1.test1: Assertion failed.",
            "testSuite0.testCase2.test1: Assertion failed.",
            }
        observed_messages = gen_failed_test_messages(example_results)
        self.assertSetEqual(expected_messages, set(observed_messages))

    def test_get_failed_tests_message(self):
        expected_message = (
            "testCase0.test1: Assertion failed."
            "\n\n"
            "testCase1.test1: Assertion failed."
            "\n\n"
            "testSuite0.testCase2.test1: Assertion failed."
            )
        observed_message = get_failed_tests_message(example_results)
        self.assertEqual(expected_message, observed_message)
