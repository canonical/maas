# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Check the current generated css matches generated css."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
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


class TestCompiledSCSS(MAASTestCase):

    def execute(self, *command):
        process = Popen(command, stdout=PIPE, stderr=STDOUT, cwd=root)
        output, _ = process.communicate()
        if len(output) != 0:
            name = "stdout/err from `%s`" % " ".join(map(quote, command))
            self.addDetail(name, Content(UTF8_TEXT, lambda: [output]))
        self.assertEqual(0, process.wait(), "failed to compile css.")

    def read_content(self, filename):
        with open(filename, "rb") as stream:
            return stream.read()

    def test_css_up_to_date(self):
        # In-tree compiles css must exist.
        in_tree_css_path = os.path.join(
            root, "src", "maasserver", "static", "css", "maas-styles.css")
        self.assertIs(
            os.path.exists(in_tree_css_path), True,
            "maas-styles.css is missing.")

        # Compile the scss into css into a temp directory.
        output_dir = self.make_dir()
        self.execute(
            "bin/sass",
            "--include-path=src/maasserver/static/scss",
            "--output-style", "compressed",
            "src/maasserver/static/scss/maas-styles.scss",
            "-o", output_dir)

        # Content should be equal. Doesn't use assertEquals so the error
        # output doesn't contain the contents.
        in_tree_css = self.read_content(in_tree_css_path)
        tmp_css = self.read_content(
            os.path.join(output_dir, "maas-styles.css"))
        if in_tree_css != tmp_css:
            self.fail("maas-styles.css is out-of-date.")
