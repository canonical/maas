# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test monkey patches."""

__all__ = []

from unittest.mock import sentinel

from maastesting.testcase import (
    MAASTestCase,
    MAASTwistedRunTest,
)
from provisioningserver.monkey import (
    add_patches_to_txtftp,
    augment_twisted_deferToThreadPool,
)
from testtools.deferredruntest import assert_fails_with
import tftp.datagram
from twisted.internet.defer import Deferred
from twisted.internet.threads import deferToThread


class TestAddTermErrorCodeToTFTP(MAASTestCase):

    def test_adds_error_code_8(self):
        self.patch(tftp.datagram, 'errors', {})
        add_patches_to_txtftp()
        self.assertIn(8, tftp.datagram.errors)
        self.assertEqual(
            "Terminate transfer due to option negotiation",
            tftp.datagram.errors.get(8))

    def test_skips_adding_error_code_if_already_present(self):
        self.patch(tftp.datagram, 'errors', {8: sentinel.error_8})
        add_patches_to_txtftp()
        self.assertEqual(
            sentinel.error_8, tftp.datagram.errors.get(8))


class TestAugmentDeferToThreadPool(MAASTestCase):
    """Tests for `augment_twisted_deferToThreadPool`."""

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    def setUp(self):
        super(TestAugmentDeferToThreadPool, self).setUp()
        augment_twisted_deferToThreadPool()

    def test_functions_returning_Deferreds_from_threads_crash(self):
        return assert_fails_with(deferToThread(Deferred), TypeError)

    def test_functions_returning_other_from_threads_are_okay(self):
        return deferToThread(round, 12.34).addCallback(self.assertEqual, 12)
