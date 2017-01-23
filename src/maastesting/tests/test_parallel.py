# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maastesting.parallel`."""

__all__ = []

import types

from maastesting.testcase import MAASTestCase
from testtools.matchers import IsInstance


class TestSmoke(MAASTestCase):
    """Trivial smoke test."""

    def test_imports_cleanly(self):
        from maastesting import parallel
        self.assertThat(parallel, IsInstance(types.ModuleType))
