# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Fixtures for testing `driver_parameters`."""

from copy import deepcopy
from functools import wraps

from fixtures import Fixture
from testtools import monkey

from maasserver.clusterrpc import driver_parameters
from provisioningserver.drivers.power.registry import PowerDriverRegistry


class StaticDriverTypesFixture(Fixture):
    """Prevents communication with racks when querying driver types.

    This patches out the `get_all_power_types` and
    `get_all_pod_types_from_racks` call. It's a common enough requirement
    that it's been folded into a fixture. This prevents communication with a
    non-existent rack controller when fetching driver types.
    """

    def _setUp(self):
        self._interceptPowerTypesQuery()

    def _interceptPowerTypesQuery(self):
        power_types = PowerDriverRegistry.get_schema(
            detect_missing_packages=False
        )

        @wraps(driver_parameters.get_all_power_types)
        def get_all_power_types():
            # Callers can mutate this, so deep copy.
            return deepcopy(power_types)

        restore = monkey.patch(
            driver_parameters, "get_all_power_types", get_all_power_types
        )
        self.addCleanup(restore)
