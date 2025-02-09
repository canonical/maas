# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Load all pod drivers."""

from jsonschema import validate

from provisioningserver.drivers.pod import JSON_POD_DRIVERS_SCHEMA
from provisioningserver.drivers.pod.lxd import LXDPodDriver
from provisioningserver.drivers.pod.virsh import VirshPodDriver
from provisioningserver.utils.registry import Registry


class PodDriverRegistry(Registry):
    """Registry for pod drivers."""

    @classmethod
    def get_schema(cls, detect_missing_packages=True):
        """Returns the full schema for the registry."""
        schemas = [
            driver.get_schema(detect_missing_packages=detect_missing_packages)
            for _, driver in cls
        ]
        validate(schemas, JSON_POD_DRIVERS_SCHEMA)
        return schemas


pod_drivers = [LXDPodDriver(), VirshPodDriver()]
for driver in pod_drivers:
    PodDriverRegistry.register_item(driver.name, driver)
