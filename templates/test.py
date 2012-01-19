# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""..."""

__metaclass__ = type
__all__ = []

from maas.testing import TestCase


class TestSomething(TestCase):

    #resources = [...]

    def test_something(self):
        self.assertTrue(1)
