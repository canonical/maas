# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check there's no lint in the tree."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from subprocess import check_call
from unittest import skip

from maastesting import root
from maastesting.testcase import MAASTestCase


class TestLint(MAASTestCase):

    @skip(
        "XXX: GavinPanella 2014-01-09 bug=1267472: "
        "This needs altering once the new package structure is in place.")
    def test_that_there_is_no_lint_in_the_tree(self):
        check_call(("make", "-C", root, "lint"))
