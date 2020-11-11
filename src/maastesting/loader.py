# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test loader for MAAS and its applications."""


import unittest


class MAASTestLoader(unittest.TestLoader):
    """Scan modules for tests by default.

    This discovers tests using `unittest.TestLoader.discover` when
    `loadTestsFromName` is called. This is not standard behaviour, but
    it's here to help hook into setuptools' testing support.

    Refer to as ``maastesting.loader:MAASTestLoader`` in ``setup.py``.
    """

    def loadTestsFromName(self, name, module=None):
        assert module is None, (
            "Module %r is confusing. This method expects the name passed "
            "in to actually be a filesystem path from which to start test "
            "discovery. It doesn't know what to do when a module object is "
            "passed in too. Sorry, either this is not the class you're "
            "looking for, or you're doing it wrong." % (module,)
        )
        return self.discover(name)
