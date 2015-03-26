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

from difflib import unified_diff
from itertools import ifilter
from os import (
    mkdir,
    walk,
)
from os.path import (
    join,
    relpath,
)
from pipes import quote
from shutil import (
    copy2,
    rmtree,
)
from subprocess import (
    PIPE,
    Popen,
    STDOUT,
)
from tempfile import mkdtemp

from maastesting import root
from maastesting.testcase import MAASTestCase
from testtools.content import (
    Content,
    UTF8_TEXT,
)


class TestLint(MAASTestCase):

    def execute(self, *command):
        process = Popen(command, stdout=PIPE, stderr=STDOUT)
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % " ".join(map(quote, command))
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
        self.assertEqual(0, process.wait(), "(return code is not zero)")

    def test_that_there_is_no_lint_in_the_tree(self):
        self.execute("make", "--quiet", "-C", root, "lint")

    def test_that_imports_are_formatted(self):
        # We're going to export all Python source code to a new, freshly
        # created, tree, then run `make format` in it.
        root_export = mkdtemp(prefix=".export.", dir=root)
        self.addCleanup(rmtree, root_export, ignore_errors=True)

        # Useful predicates.
        p_visible = lambda name: not name.startswith(".")
        p_is_python = lambda name: name.endswith(".py")

        # Copy all visible Python source files over.
        for dirpath, dirnames, filenames in walk(root):
            dirnames[:] = ifilter(p_visible, dirnames)
            dirpath_export = join(root_export, relpath(dirpath, start=root))
            for dirname in dirnames:
                mkdir(join(dirpath_export, dirname))
            for filename in ifilter(p_visible, filenames):
                if p_is_python(filename):
                    src = join(dirpath, filename)
                    dst = join(dirpath_export, filename)
                    copy2(src, dst)

        # We'll need the Makefile and format-imports too.
        copy2(join(root, "Makefile"), root_export)
        copy2(
            join(root, "utilities", "format-imports"),
            join(root_export, "utilities", "format-imports"))

        # Format imports in the exported tree.
        self.execute("make", "--quiet", "-C", root_export, "format")

        # This will record a unified diff between the original source code and
        # the reformatted source code, should there be any.
        diff = []

        # For each file in the export, compare it to its counterpart in the
        # original tree.
        for dirpath, dirnames, filenames in walk(root_export):
            dirpath_relative = relpath(dirpath, start=root_export)
            dirpath_original = join(root, dirpath_relative)
            for filename in ifilter(p_is_python, filenames):
                filepath_original = join(dirpath_original, filename)
                with open(filepath_original, "rb") as file_original:
                    file_lines_original = file_original.readlines()
                filepath_formatted = join(dirpath, filename)
                with open(filepath_formatted, "rb") as file_formatted:
                    file_lines_formatted = file_formatted.readlines()
                diff.extend(unified_diff(
                    file_lines_original, file_lines_formatted,
                    filepath_original, filepath_formatted))

        if len(diff) != 0:
            self.addDetail("diff", Content(UTF8_TEXT, lambda: diff))
            self.fail(
                "Some imports are not formatted; see the diff for the "
                "missing changes. Use `make format` to address them.")
