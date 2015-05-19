# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the tgt service driver."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maastesting.testcase import MAASTestCase
from provisioningserver.drivers.service import SERVICE_STATE
from provisioningserver.drivers.service.tgt import TGTService


class TestTGTService(MAASTestCase):

    def test_service_name(self):
        tgt = TGTService()
        self.assertEqual("tgt", tgt.service_name)

    def test_get_expected_state(self):
        tgt = TGTService()
        self.assertEqual(SERVICE_STATE.ON, tgt.get_expected_state())
