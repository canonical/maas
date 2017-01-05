# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fixtures for testing `driver_parameters`."""

__all__ = [
    'StaticDriverTypesFixture',
    ]

from unittest.mock import Mock

from fixtures import Fixture
from maasserver.clusterrpc import driver_parameters
from provisioningserver.drivers.chassis.registry import ChassisDriverRegistry
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from testtools import monkey


class StaticDriverTypesFixture(Fixture):
    """Prevents communication with racks when querying driver types.

    This patches out the `get_all_power_types_from_racks` and
    `get_all_chassis_types_from_racks` call. It's a common enough requirement
    that it's been folded into a fixture.
    """

    def setUp(self):
        super(StaticDriverTypesFixture, self).setUp()
        # This patch prevents communication with a non-existent rack
        # controller when fetching driver types.
        power_types = PowerDriverRegistry.get_schema(
            detect_missing_packages=False)
        chassis_types = ChassisDriverRegistry.get_schema(
            detect_missing_packages=False)
        restore = monkey.patch(
            driver_parameters, 'get_all_power_types_from_racks',
            Mock(return_value=power_types))
        self.addCleanup(restore)
        restore = monkey.patch(
            driver_parameters, 'get_all_chassis_types_from_racks',
            Mock(return_value=chassis_types))
        self.addCleanup(restore)
