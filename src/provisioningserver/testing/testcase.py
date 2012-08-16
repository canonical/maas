# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Provisioningserver-specific test-case classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'PservTestCase',
    ]

from maastesting import testcase
from provisioningserver.cache import cache as pserv_cache


class PservTestCase(testcase.TestCase):

    def setUp(self):
        super(PservTestCase, self).setUp()
        self.addCleanup(pserv_cache.clear)
