# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the Neighbour model."""


from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import IsNonEmptyString


class TestNeighbourModel(MAASServerTestCase):
    def test_mac_organization(self):
        neighbour = factory.make_Neighbour(mac_address="48:51:b7:00:00:00")
        self.assertThat(neighbour.mac_organization, IsNonEmptyString)
