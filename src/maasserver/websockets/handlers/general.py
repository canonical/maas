# Copyright 2015-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The general handler for the WebSocket connection."""


from collections import OrderedDict

import petname

from maasserver.certificates import get_maas_certificate
from maasserver.clusterrpc.driver_parameters import get_all_power_types
from maasserver.enum import (
    BOND_LACP_RATE_CHOICES,
    BOND_MODE_CHOICES,
    BOND_XMIT_HASH_POLICY_CHOICES,
    NODE_TYPE,
)
from maasserver.models.bootresource import BootResource
from maasserver.models.config import Config
from maasserver.models.controllerinfo import (
    get_maas_version,
    get_target_version,
)
from maasserver.models.node import Node
from maasserver.models.packagerepository import PackageRepository
from maasserver.node_action import ACTIONS_DICT
from maasserver.permissions import NodePermission
from maasserver.utils.certificates import (
    generate_certificate,
    get_maas_client_cn,
)
from maasserver.utils.osystems import (
    list_all_usable_hwe_kernels,
    list_all_usable_osystems,
    list_all_usable_releases,
    list_hwe_kernel_choices,
    list_osystem_choices,
    list_release_choices,
)
from maasserver.websockets.base import dehydrate_datetime, Handler
from provisioningserver.boot import BootMethodRegistry


class GeneralHandler(Handler):
    """Provides general methods that can be called from the client."""

    class Meta:
        allowed_methods = [
            "architectures",
            "bond_options",
            "components_to_disable",
            "default_min_hwe_kernel",
            "device_actions",
            "generate_client_certificate",
            "hwe_kernels",
            "known_architectures",
            "known_boot_architectures",
            "machine_actions",
            "min_hwe_kernels",
            "osinfo",
            "pockets_to_disable",
            "power_types",
            "rack_controller_actions",
            "random_hostname",
            "region_and_rack_controller_actions",
            "region_controller_actions",
            "release_options",
            "target_version",
            "tls_certificate",
            "version",
            "vault_enabled",
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

    def components_to_disable(self, params):
        "Return compoennts that can be disable for default Ubuntu archives"
        return PackageRepository.objects.get_components_to_disable()

    def hwe_kernels(self, params):
        """Return all supported hwe_kernels."""
        return list_hwe_kernel_choices(BootResource.objects.get_kernels())

    def min_hwe_kernels(self, params):
        """Return all supported min_hwe_kernels.

        This filters out all non-generic kernel flavors. The user can select
        the flavor during deployment.
        """
        return list_hwe_kernel_choices(
            BootResource.objects.get_supported_kernel_compatibility_levels()
        )

    def default_min_hwe_kernel(self, params):
        """Return the default_min_hwe_kernel."""
        return Config.objects.get_config("default_min_hwe_kernel")

    def osinfo(self, params):
        """Return all available operating systems and releases information."""
        releases = list_all_usable_releases()
        osystems = list_all_usable_osystems(releases)
        kernels = list_all_usable_hwe_kernels(releases)
        return {
            "osystems": list_osystem_choices(osystems, include_default=False),
            "releases": list_release_choices(releases, include_default=False),
            "kernels": kernels,
            "default_osystem": Config.objects.get_config("default_osystem"),
            "default_release": Config.objects.get_config(
                "default_distro_series"
            ),
        }

    def dehydrate_actions(self, actions):
        """Dehydrate all the actions."""
        return [
            {
                "name": name,
                "title": action.display,
                "sentence": action.display_sentence,
                "type": action.action_type,
            }
            for name, action in actions.items()
        ]

    def _node_actions(self, params, node_type):
        # Only admins can perform controller actions
        if not self.user.is_superuser and node_type in [
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ]:
            return []

        actions = OrderedDict()
        for name, action in ACTIONS_DICT.items():
            if node_type not in action.for_type:
                continue
            if (
                action.get_permission(node_type) == NodePermission.admin
                and not self.user.is_superuser
            ):
                continue
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
        return self._node_actions(params, NODE_TYPE.REGION_AND_RACK_CONTROLLER)

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
        return str(get_maas_version())

    def target_version(self, params):
        """Return the deployment target version."""
        target_version = get_target_version()
        return {
            "version": str(target_version.version),
            "snap_channel": str(target_version.snap_channel),
            "snap_cohort": target_version.snap_cohort,
            "first_reported": target_version.first_reported,
        }

    def power_types(self, params):
        """Return all power types."""
        return get_all_power_types()

    def release_options(self, params):
        """Return global release options."""
        return {
            "erase": Config.objects.get_config(
                "enable_disk_erasing_on_release"
            ),
            "secure_erase": Config.objects.get_config(
                "disk_erase_with_secure_erase"
            ),
            "quick_erase": Config.objects.get_config(
                "disk_erase_with_quick_erase"
            ),
        }

    def known_boot_architectures(self, params):
        """Return all known boot architectures."""
        return [
            {
                "name": boot_method.name,
                "bios_boot_method": boot_method.bios_boot_method,
                "bootloader_arches": "/".join(boot_method.bootloader_arches),
                "arch_octet": boot_method.arch_octet,
                "protocol": (
                    "http"
                    if boot_method.http_url or boot_method.user_class
                    else "tftp"
                ),
            }
            for _, boot_method in BootMethodRegistry
            if boot_method.arch_octet or boot_method.user_class
        ]

    def generate_client_certificate(self, params):
        """Generate a client X509 client certificate.

        This can be used for something like a LXD VM host. The
        certificate is not stored in the DB, so that caller is
        responsible for keeping track of it and pass it around.

        If object_name is passed, the certificate's CN will be
        $objectname@$maas_name. If not, the CN will be $maas_name.
        """
        cert = generate_certificate(
            get_maas_client_cn(params.get("object_name"))
        )
        return {
            "CN": cert.cn(),
            "certificate": cert.certificate_pem(),
            "expiration": dehydrate_datetime(cert.expiration()),
            "fingerprint": cert.cert_hash(),
            "private_key": cert.private_key_pem(),
        }

    def tls_certificate(self, params):
        """Returns information about certificate used by HTTP reverse proxy.

        All requests to MAAS API are proxied via HTTP reverse proxy.
        If TLS is enabled, then HTTPS used for communication.
        """
        cert = get_maas_certificate()
        if cert is None:
            return None
        return {
            "CN": cert.cn(),
            "certificate": cert.certificate_pem(),
            "expiration": dehydrate_datetime(cert.expiration()),
            "fingerprint": cert.cert_hash(),
        }

    def vault_enabled(self, params):
        """Tells whether Vault integration is enabled or not"""
        return Config.objects.get_config("vault_enabled", False)
