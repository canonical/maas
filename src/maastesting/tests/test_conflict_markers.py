# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check there's no conflict markers in the code."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from pipes import quote
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

# Do not use '=======' as a conflict marker since it's
# used in docstrings.
# Express the conflict markers so that this very file won't contain
# them.
CONFLICT_MARKERS = "<" * 7, ">" * 7


class TestConflictMarkers(MAASTestCase):

    def execute(self, *command):
        process = Popen(command, stdout=PIPE, stderr=STDOUT, cwd=root)
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % " ".join(map(quote, command))
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
            self.assertEqual('', output, "Conflict markers present!")
        self.assertEqual(1, process.wait(), "(return code is not one)")

    def test_no_conflict_markers(self):
        command = ["egrep", "-rI", "--exclude=*~", "--exclude-dir=include"]
        command.append("|".join(CONFLICT_MARKERS))
        self.execute(*command)
