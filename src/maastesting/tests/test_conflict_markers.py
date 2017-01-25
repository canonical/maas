# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check there's no conflict markers in the code."""

__all__ = []

from os.path import (
    isdir,
    join,
)
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)
from unittest import skipIf

from maastesting import root
from maastesting.testcase import MAASTestCase
from testtools.content import (
    Content,
    UTF8_TEXT,
)


class TestConflictMarkers(MAASTestCase):
    """Search for merge conflict markers if this is a branch."""

    @skipIf(not isdir(join(root, ".bzr")), "Not a branch.")
    def test_no_conflict_markers(self):
        # Do not search for '=======' as a conflict marker since it's used in
        # docstrings, search for angle brackets instead. Express the conflict
        # markers as a regular expression so that this very file won't match.
        command = (
            "bzr ls --kind=file --recursive --versioned --null | "
            "xargs -r0 egrep -I '[<]{7}|[>]{7}' -C 3")
        process = Popen(
            command, shell=True, stdout=PIPE, stderr=STDOUT, cwd=root)
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % command
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
            self.fail("Conflict markers present!")
        # Don't check the process's exit code because xargs muddles things.
        # Checking the output should suffice.
