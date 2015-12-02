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
    "Crochet",
    "main",
    "Select",
]

import inspect
import logging

from nose.core import TestProgram
from nose.plugins.base import Plugin
from twisted.python.filepath import FilePath


class Crochet(Plugin):
    """Start the Twisted reactor via Crochet."""

    name = "crochet"
    option_no_setup = "%s_no_setup" % name
    log = logging.getLogger('nose.plugins.%s' % name)

    def options(self, parser, env):
        """Add options to Nose's parser.

        :attention: This is part of the Nose plugin contract.
        """
        super(Crochet, self).options(parser, env)
        parser.add_option(
            "--%s-no-setup" % self.name, dest=self.option_no_setup,
            action="store_true", default=False, help=(
                "Initialize the crochet library with no side effects."
            ),
        )

    def configure(self, options, conf):
        """Configure, based on the parsed options.

        :attention: This is part of the Nose plugin contract.
        """
        super(Crochet, self).configure(options, conf)
        if self.enabled:
            import crochet

            if getattr(options, self.option_no_setup):
                crochet.no_setup()
            else:
                crochet.setup()

    def help(self):
        """Used in the --help text.

        :attention: This is part of the Nose plugin contract.
        """
        return inspect.getdoc(self)


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

    Specifically the `Crochet` and `Select` plugins. At the command-line it's
    still necessary to enable these with the flags ``--with-crochet`` and/or
    ``--with-select``.
    """
    return TestProgram(addplugins=[Crochet(), Select()])
