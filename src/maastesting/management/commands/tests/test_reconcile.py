# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.management.commands.reconcile`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maastesting.testcase import TestCase
from maastesting.management.commands.reconcile import (
    guess_architecture_from_profile,
    )


class TestFunctions(TestCase):

    def test_guess_architecture_from_profile(self):
        guess = guess_architecture_from_profile
        self.assertEqual("i386", guess("a-i386-profile"))
        self.assertEqual("amd64", guess("amd64-profile"))
        self.assertEqual("amd64", guess("profile-for-x86_64"))
        self.assertEqual(None, guess("profile-for-arm"))
