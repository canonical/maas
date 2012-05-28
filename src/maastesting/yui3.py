# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for dealing with YUI3."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "extract_tests",
    "gen_failed_test_messages",
    "get_failed_tests_message",
    ]


def extract_tests(results):
    """Extract tests from a YUI3 test result object.

    See `TestSuite-Level Events`_ for details of the test result object form.

    .. _TestSuite-Level Events:
      http://yuilibrary.com/yui/docs/test/#testsuite-level-events

    """
    accumulator = {}
    _extract_tests(results, accumulator)
    return accumulator


def _extract_tests(results, accumulator, *stack):
    """Helper for `extract_tests`."""
    if isinstance(results, dict):
        if results["type"] == "test":
            name = ".".join(reversed(stack))
            accumulator[name] = results
        else:
            for name, value in results.items():
                _extract_tests(value, accumulator, name, *stack)


def gen_failed_test_messages(results):
    """Yield test failure messages from the given results.

    @param results: See `extract_tests`.
    """
    for name, test in extract_tests(results).items():
        if test["result"] != "pass":
            yield "%s: %s" % (name, test["message"])


def get_failed_tests_message(results):
    """Return a complete error message for the given results.

    @param results: See `extract_tests`.
    """
    messages = gen_failed_test_messages(results)
    return "\n\n".join(sorted(messages))
