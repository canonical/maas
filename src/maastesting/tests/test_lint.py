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

from subprocess import (
    PIPE,
    Popen,
    STDOUT,
    )

from maastesting import root
from maastesting.testcase import MAASTestCase
from testtools.content import (
    Content,
    UTF8_TEXT,
    )


class TestLint(MAASTestCase):

    def test_that_there_is_no_lint_in_the_tree(self):
        command = "make", "-C", root, "lint"
        process = Popen(command, stdout=PIPE, stderr=STDOUT)
        output, _ = process.communicate()
        self.addDetail("output", Content(UTF8_TEXT, lambda: [output]))
        self.assertEqual(0, process.wait(), "(return code is not zero)")
