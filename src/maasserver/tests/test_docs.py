# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test MAAS's documentation."""

__all__ = []

import doctest
import io
from pathlib import Path

from maasserver.testing.testcase import MAASServerTestCase
from maastesting import root


docs = Path(root).joinpath("docs")


class TestDoc(MAASServerTestCase):
    """Test each page of MAAS's documentation as doctest."""

    scenarios = (
        (str(path.relative_to(docs)), dict(path=path))
        for path in docs.rglob("*.rst")
    )

    parser = doctest.DocTestParser()
    optionflags = (
        doctest.ELLIPSIS |
        doctest.NORMALIZE_WHITESPACE |
        doctest.REPORT_NDIFF
    )

    @classmethod
    def makeRunner(cls, test):
        runner = doctest.DocTestRunner(
            optionflags=cls.optionflags, verbose=False)
        runner.DIVIDER = "-" * len(runner.DIVIDER)
        return runner

    @classmethod
    def loadTest(cls, path):
        doc = path.read_text("utf-8")
        globs = {"__file__": str(path)}
        return cls.parser.get_doctest(
            doc, globs, path.name, str(path), 0)

    def test(self):
        output = io.StringIO()
        test = self.loadTest(self.path)
        runner = self.makeRunner(test)
        failures, tries = runner.run(test, out=output.write)
        if failures != 0:
            raise self.failureException(output.getvalue())
