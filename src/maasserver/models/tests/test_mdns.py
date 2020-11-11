# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the mDNS model."""


from testtools.matchers import Equals

from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestMDNSModel(MAASServerTestCase):
    def test_accepts_invalid_hostname(self):
        mdns = factory.make_MDNS(hostname="Living room")
        # Expect no exception.
        self.assertThat(mdns.hostname, Equals("Living room"))
