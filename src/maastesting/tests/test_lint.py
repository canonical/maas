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

from subprocess import STDOUT

from maastesting import root
from maastesting.testcase import MAASTestCase
from provisioningserver.utils import call_capture_and_check


class TestLint(MAASTestCase):

    def test_that_there_is_no_lint_in_the_tree(self):
        call_capture_and_check(("make", "-C", root, "lint"), stderr=STDOUT)
