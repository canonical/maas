# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Testing helpers for the `neighbours` service."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "NeighboursServiceFixture",
]

import fixtures
import provisioningserver
from provisioningserver.pserv_services.neighbours import NeighboursService
from provisioningserver.utils.network import NeighboursProtocol
from testtools import monkey
from twisted.application.service import MultiService


class NeighboursServiceFixture(fixtures.Fixture):
    """Configure a `NeighboursService`, left inert by default."""

    def setUp(self):
        super(NeighboursServiceFixture, self).setUp()
        services = MultiService()
        self.service = NeighboursService()
        self.service.setName("neighbours")
        self.service.setServiceParent(services)
        self.addCleanup(monkey.patch(
            provisioningserver, "services", services))

    def setFromOutput(self, output):
        results = NeighboursProtocol.parseOutput(output.splitlines())
        collated = NeighboursProtocol.collateNeighbours(results)
        self.service.set(collated)
