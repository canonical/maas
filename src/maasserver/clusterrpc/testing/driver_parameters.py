# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fixtures for testing `driver_parameters`."""

__all__ = [
    'StaticDriverTypesFixture',
    ]

from copy import deepcopy
from functools import wraps

from fixtures import Fixture
from maasserver.clusterrpc import driver_parameters
from provisioningserver.drivers.power.registry import PowerDriverRegistry
from testtools import monkey


class StaticDriverTypesFixture(Fixture):
    """Prevents communication with racks when querying driver types.

    This patches out the `get_all_power_types_from_racks` and
    `get_all_pod_types_from_racks` call. It's a common enough requirement
    that it's been folded into a fixture. This prevents communication with a
    non-existent rack controller when fetching driver types.
    """

    def _setUp(self):
        self._interceptPowerTypesQuery()

    def _interceptPowerTypesQuery(self):
        power_types = PowerDriverRegistry.get_schema(
            detect_missing_packages=False)

        @wraps(driver_parameters.get_all_power_types_from_racks)
        def get_all_power_types_from_racks(
                controllers=None, ignore_errors=True):
            # Callers can mutate this, so deep copy.
            return deepcopy(power_types)

        restore = monkey.patch(
            driver_parameters, 'get_all_power_types_from_racks',
            get_all_power_types_from_racks)
        self.addCleanup(restore)
