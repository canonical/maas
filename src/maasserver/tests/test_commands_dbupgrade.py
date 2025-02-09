# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `dbupgrade` management command."""

from django.core.management import call_command

from maasserver.testing.testcase import MAASTransactionServerTestCase


class TestDBUpgrade(MAASTransactionServerTestCase):
    def test_dbupgrade(self):
        # Test is this doesn't fail.
        call_command("dbupgrade")
