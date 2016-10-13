# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The general handler for the WebSocket connection."""

__all__ = [
    "GeneralHandler",
    ]

from collections import OrderedDict

from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
)
from maasserver.enum import (
    BOND_LACP_RATE_CHOICES,
    BOND_MODE_CHOICES,
    BOND_XMIT_HASH_POLICY_CHOICES,
    NODE_PERMISSION,
    NODE_TYPE,
)
from maasserver.models.bootresource import BootResource
from maasserver.models.config import Config
from maasserver.models.node import Node
from maasserver.models.packagerepository import PackageRepository
from maasserver.node_action import ACTIONS_DICT
from maasserver.utils.orm import reload_object
from maasserver.utils.osystems import (
    list_all_usable_hwe_kernels,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_hwe_kernel_choices,
    list_osystem_choices,
    list_release_choices,
)
from maasserver.utils.version import get_maas_version_ui
from maasserver.websockets.base import Handler
import petname


class GeneralHandler(Handler):
    """Provides general methods that can be called from the client."""

    class Meta:
        allowed_methods = [
            'architectures',
            'known_architectures',
            'pockets_to_disable',
            'hwe_kernels',
            'min_hwe_kernels',
            'default_min_hwe_kernel',
            'osinfo',
            'machine_actions',
            'device_actions',
            'rack_controller_actions',
            'region_controller_actions',
            'region_and_rack_controller_actions',
            'random_hostname',
            'bond_options',
            'version',
            'power_types',
            'release_options',
            ]

    def architectures(self, params):
        """Return all usable architectures."""
        return BootResource.objects.get_usable_architectures()

    def known_architectures(self, params):
        """Return all known architectures, usable or not."""
        return PackageRepository.objects.get_known_architectures()

    def pockets_to_disable(self, params):
        """Return pockets that can be disabled."""
        return PackageRepository.objects.get_pockets_to_disable()

    def hwe_kernels(self, params):
        """Return all supported hwe_kernels."""
        return list_hwe_kernel_choices(
            BootResource.objects.get_usable_hwe_kernels())

    def min_hwe_kernels(self, params):
        """Return all supported min_hwe_kernels.

        This filters out all non-generic kernel flavors. The user can select
        the flavor during deployment.
        """
        return list_hwe_kernel_choices(
            BootResource.objects.get_usable_hwe_kernels()
        )

    def default_min_hwe_kernel(self, params):
        """Return the default_min_hwe_kernel."""
        return Config.objects.get_config('default_min_hwe_kernel')

    def osinfo(self, params):
        """Return all available operating systems and releases information."""
        osystems = list_all_usable_osystems()
        releases = list_all_usable_releases(osystems)
        kernels = list_all_usable_hwe_kernels(releases)
        return {
            "osystems": list_osystem_choices(osystems, include_default=False),
            "releases": list_release_choices(releases, include_default=False),
            "kernels": kernels,
            "default_osystem": Config.objects.get_config("default_osystem"),
            "default_release": Config.objects.get_config(
                "default_distro_series"),
        }

    def dehydrate_actions(self, actions):
        """Dehydrate all the actions."""
        return [
            {
                "name": name,
                "title": action.display,
                "sentence": action.display_sentence,
            }
            for name, action in actions.items()
            ]

    def _node_actions(self, params, node_type):
        # Only admins can perform controller actions
        if (not reload_object(self.user).is_superuser and node_type in [
                NODE_TYPE.RACK_CONTROLLER, NODE_TYPE.REGION_CONTROLLER,
                NODE_TYPE.REGION_AND_RACK_CONTROLLER]):
            return {}

        actions = OrderedDict()
        for name, action in ACTIONS_DICT.items():
            if (action.node_permission == NODE_PERMISSION.ADMIN and
                    not reload_object(self.user).is_superuser):
                continue
            elif node_type in action.for_type:
                actions[name] = action
        return self.dehydrate_actions(actions)

    def machine_actions(self, params):
        """Return all possible machine actions."""
        return self._node_actions(params, NODE_TYPE.MACHINE)

    def device_actions(self, params):
        """Return all possible device actions."""
        return self._node_actions(params, NODE_TYPE.DEVICE)

    def region_controller_actions(self, params):
        """Return all possible region controller actions."""
        return self._node_actions(params, NODE_TYPE.REGION_CONTROLLER)

    def rack_controller_actions(self, params):
        """Return all possible rack controller actions."""
        return self._node_actions(params, NODE_TYPE.RACK_CONTROLLER)

    def region_and_rack_controller_actions(self, params):
        """Return all possible region and rack controller actions."""
        return self._node_actions(
            params, NODE_TYPE.REGION_AND_RACK_CONTROLLER)

    def random_hostname(self, params):
        """Return a random hostname."""
        while True:
            new_hostname = petname.Generate(2, "-")
            try:
                Node.objects.get(hostname=new_hostname)
            except Node.DoesNotExist:
                return new_hostname
        return ""

    def bond_options(self, params):
        """Return all the possible bond options."""
        return {
            "modes": BOND_MODE_CHOICES,
            "lacp_rates": BOND_LACP_RATE_CHOICES,
            "xmit_hash_policies": BOND_XMIT_HASH_POLICY_CHOICES,
        }

    def version(self, params):
        """Return the MAAS version."""
        return get_maas_version_ui()

    def power_types(self, params):
        """Return all power types."""
        return get_all_power_types_from_clusters()

    def release_options(self, params):
        """Return global release options."""
        return {
            "erase": Config.objects.get_config(
                "enable_disk_erasing_on_release"),
            "secure_erase": Config.objects.get_config(
                "disk_erase_with_secure_erase"),
            "quick_erase": Config.objects.get_config(
                "disk_erase_with_quick_erase"),
        }
