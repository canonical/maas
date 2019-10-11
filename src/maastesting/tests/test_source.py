# Copyright 2015-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check MAAS's source directly for preventable mistakes."""

__all__ = []

from os.path import isdir, join
from subprocess import PIPE, Popen, STDOUT
from unittest import skipIf

from maastesting import root
from maastesting.testcase import MAASTestCase
from testtools.content import Content, UTF8_TEXT


class TestSource(MAASTestCase):
    @skipIf(not isdir(join(root, ".git")), "Not a branch.")
    def test_no_conflict_markers(self):
        # Do not search for '=======' as a conflict marker since it's used in
        # docstrings, search for angle brackets instead. Express the conflict
        # markers as a regular expression so that this very file won't match.
        command = "git ls-files -z | xargs -r0 egrep -snI '[<]{7}|[>]{7}' -C 3"
        process = Popen(
            command, shell=True, stdout=PIPE, stderr=STDOUT, cwd=root
        )
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % command
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
            self.fail("Conflict markers present!")
        # Don't check the process's exit code because xargs muddles things.
        # Checking the output should suffice.

    @skipIf(not isdir(join(root, ".git")), "Not a branch.")
    def test_no_yaml_load_or_dump(self):
        # PyYAML's load and dump functions are unsafe by default.
        command = (
            "git ls-files -z | "
            "xargs -r0 egrep -snI '\\byaml[.](load|dump)\\b' -C 3"
        )
        process = Popen(
            command, shell=True, stdout=PIPE, stderr=STDOUT, cwd=root
        )
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % command
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
            # The string breaks in the following message are deliberate, to
            # prevent this test from matching itself.
            self.fail(
                "Do not use yaml"
                ".load or yaml"
                ".dump: use "
                "yaml.safe_load or yaml.safe_dump instead!"
            )
        # Don't check the process's exit code because xargs muddles things.
        # Checking the output should suffice.
