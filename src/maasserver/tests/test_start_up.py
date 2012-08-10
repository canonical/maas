# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the start up utility."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver import start_up
from maasserver.models.nodegroup import NodeGroup
from maastesting.fakemethod import FakeMethod
from maastesting.testcase import TestCase


class TestStartUp(TestCase):
    """Testing for the method `start_up`."""

    def test_start_up_calls_setup_maas_avahi_service(self):
        recorder = FakeMethod()
        self.patch(start_up, 'setup_maas_avahi_service', recorder)
        start_up.start_up()
        self.assertEqual(
            (1, [()]),
            (recorder.call_count, recorder.extract_args()))

    def test_start_up_calls_write_full_dns_config(self):
        recorder = FakeMethod()
        self.patch(start_up, 'write_full_dns_config', recorder)
        start_up.start_up()
        self.assertEqual(
            (1, [()]),
            (recorder.call_count, recorder.extract_args()))

    def test_start_up_creates_master_nodegroup(self):
        start_up.start_up()
        self.assertEqual(1, NodeGroup.objects.all().count())
