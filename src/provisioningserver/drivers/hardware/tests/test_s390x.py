# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `provisioningserver.drivers.hardware.s390x`.
"""

__all__ = []

import zhmcclient
from zhmcclient_mock import FakedSession

from maastesting.testcase import (
    MAASTestCase,
)
from provisioningserver.drivers.hardware import s390x


class TestS390XHMCClient(MAASTestCase):
    """Tests for `S390XHMCClient`."""

    def setUp(self):
        super().setUp()
        self.session_mock = self.patch(s390x, 'Session')
        self.faked_session = FakedSession(
            'example.com', 'hmc-test', '2.13.1', '1.8')
        self.session_mock.return_value = self.faked_session
        self.faked_session.hmc.cpcs.add(
            {'name': 'cpc-test',
             'dpm-enabled': True,
             })
        client = zhmcclient.Client(self.faked_session)
        [cpc] = client.cpcs.list()
        self.part = cpc.partitions.create(
            {'name': 'test',
             'status': 'active',
             'object-id': 'some-uuid',
             'initial-memory': 1024,
             'maximum-memory': 2048})

    def test_foo(self):
        client = s390x.S390XHMCClient('foo', 'bar', 'baz')
        self.assertEqual(
            'active',
            client.get_power_state(self.part.properties['object-id']))
