# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Nose plugins for MAAS."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "main",
    "Select",
]

import inspect
import logging

from nose.core import TestProgram
from nose.plugins.base import Plugin
from twisted.python.filepath import FilePath


class Select(Plugin):
    """Another way to limit which tests are chosen."""

    name = "select"
    option_dirs = "%s_dirs" % name
    log = logging.getLogger('nose.plugins.%s' % name)

    def __init__(self):
        super(Select, self).__init__()
        self.dirs = frozenset()

    def options(self, parser, env):
        """Add options to Nose's parser.

        :attention: This is part of the Nose plugin contract.
        """
        super(Select, self).options(parser, env)
        parser.add_option(
            "--%s-dir" % self.name, "--%s-directory" % self.name,
            dest=self.option_dirs, action="append", default=[], help=(
                "Allow test discovery in this directory. Explicitly named "
                "tests outside of this directory may still be loaded. This "
                "option can be given multiple times to allow discovery in "
                "multiple directories."
            ),
            metavar="DIR",
        )

    def configure(self, options, conf):
        """Configure, based on the parsed options.

        :attention: This is part of the Nose plugin contract.
        """
        super(Select, self).configure(options, conf)
        if self.enabled:
            # Process --${name}-dir.
            for path in getattr(options, self.option_dirs):
                self.addDirectory(path)
            if self.log.isEnabledFor(logging.DEBUG):
                self.log.debug(
                    "Limiting to the following directories "
                    "(exact matches only):")
                for path in sorted(self.dirs):
                    self.log.debug("- %s", path)

    def addDirectory(self, path):
        """Include `path` in test discovery.

        This scans all child directories of `path` and also all `parents`;
        `wantDirectory()` can then do an exact match.
        """
        start = FilePath(path)
        self.dirs = self.dirs.union(
            (fp.path for fp in start.parents()),
            (fp.path for fp in start.walk() if fp.isdir()),
        )

    def wantDirectory(self, path):
        """Rejects directories outside of the chosen few.

        :attention: This is part of the Nose plugin contract.
        """
        if path in self.dirs:
            self.log.debug("Selecting %s", path)
            return True
        else:
            self.log.debug("Rejecting %s", path)
            return False

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


def main():
    """Invoke Nose's `TestProgram` with extra plugins.

    Specifically the `Select` plugin. At the command-line it's still necessary
    to enable this plugin using ``--with-select``.
    """
    return TestProgram(addplugins=[Select()])
