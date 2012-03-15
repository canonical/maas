# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the maas package."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

import codecs
from importlib import import_module
import new
from os import path
import sys
from unittest import skipIf

from fixtures import (
    PythonPathEntry,
    TempDir,
    )
from maas import (
    find_settings,
    import_local_settings,
    import_settings,
    )
from maastesting.factory import factory
from maastesting.testcase import TestCase


class TestSettingsHelpers(TestCase):
    """Test Django settings helper functions."""

    def test_find_settings(self):
        # find_settings() returns a dict of settings from a Django-like
        # settings file. It excludes settings beginning with underscores.
        module = new.module(b"example")
        module.SETTING = factory.getRandomString()
        module._NOT_A_SETTING = factory.getRandomString()
        expected = {"SETTING": module.SETTING}
        observed = find_settings(module)
        self.assertEqual(expected, observed)

    def test_import_settings(self):
        # import_settings() copies settings from another module into the
        # caller's global scope.
        source = new.module(b"source")
        source.SETTING = factory.getRandomString()
        target = new.module(b"target")
        target._source = source
        target._import_settings = import_settings
        eval("_import_settings(_source)", vars(target))
        expected = {"SETTING": source.SETTING}
        observed = find_settings(target)
        self.assertEqual(expected, observed)

    local_settings_module = b"maas_local_settings"

    def _test_import_local_settings(self):
        # import_local_settings() copies settings from the local settings
        # module into the caller's global scope.
        target = new.module(b"target")
        target._import_local_settings = import_local_settings
        eval("_import_local_settings()", vars(target))
        source = import_module(self.local_settings_module)
        expected = find_settings(source)
        observed = find_settings(target)
        self.assertEqual(expected, observed)

    @skipIf(
        local_settings_module in sys.modules,
        "%s already imported." % local_settings_module)
    def test_import_local_settings_1(self):
        # The local settings module has not yet been imported, so fake one.
        module_dir = self.useFixture(TempDir()).path
        module_path = path.join(
            module_dir, b"%s.py" % self.local_settings_module)
        with codecs.open(module_path, "wb", "ascii") as stream:
            stream.write("SETTING = %r\n" % factory.getRandomString())
            stream.write("_NOT_A_SETTING = %r\n" % factory.getRandomString())
        self.addCleanup(sys.modules.pop, self.local_settings_module, None)
        self.useFixture(PythonPathEntry(module_dir))
        self._test_import_local_settings()

    @skipIf(
        local_settings_module not in sys.modules,
        "%s not yet imported." % local_settings_module)
    def test_import_local_settings_2(self):
        # The local settings module has been imported, so test with that.
        self._test_import_local_settings()
