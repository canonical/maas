# Copyright 2015-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbupgrade` management command."""

import os

from django.core.management import call_command

from maasserver.testing.testcase import MAASTransactionServerTestCase


class TestDBUpgrade(MAASTransactionServerTestCase):
    def test_dbupgrade(self):
        # Test is this doesn't fail.
        openfga_path = os.getcwd() + "/src/maasopenfga/build/"
        call_command("dbupgrade", openfga_path=openfga_path)
