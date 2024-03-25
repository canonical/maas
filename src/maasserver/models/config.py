# Copyright 2012-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items."""


from collections import defaultdict, namedtuple
from contextlib import suppress
import copy
from datetime import timedelta
from socket import gethostname
import uuid

from django.db.models import CharField, Manager, Model
from django.db.models.signals import post_save

from maasserver.fields import JSONObjectField
from maasserver.listener import notify_action
from provisioningserver.drivers.osystem.ubuntu import UbuntuOS
from provisioningserver.events import EVENT_TYPES

DEFAULT_OS = UbuntuOS()

DNSSEC_VALIDATION_CHOICES = [
    ("auto", "Automatic (use default root key)"),
    ("yes", "Yes (manually configured root key)"),
    ("no", "No (Disable DNSSEC; useful when upstream DNS is misconfigured)"),
]

NETWORK_DISCOVERY_CHOICES = [("enabled", "Enabled"), ("disabled", "Disabled")]


def _timedelta_to_whole_seconds(**kwargs) -> int:
    """Convert arbitrary timedelta to whole seconds."""
    return int(timedelta(**kwargs).total_seconds())


ACTIVE_DISCOVERY_INTERVAL_CHOICES = [
    (0, "Never (disabled)"),
    (_timedelta_to_whole_seconds(days=7), "Every week"),
    (_timedelta_to_whole_seconds(days=1), "Every day"),
    (_timedelta_to_whole_seconds(hours=12), "Every 12 hours"),
    (_timedelta_to_whole_seconds(hours=6), "Every 6 hours"),
    (_timedelta_to_whole_seconds(hours=3), "Every 3 hours"),
    (_timedelta_to_whole_seconds(hours=1), "Every hour"),
    (_timedelta_to_whole_seconds(minutes=30), "Every 30 minutes"),
    (_timedelta_to_whole_seconds(minutes=10), "Every 10 minutes"),
]


def get_default_config():
    """
    :return: A dictionary mapping default settings keys to default values.
    """
    return {
        # Ubuntu section configuration.
        "commissioning_osystem": DEFAULT_OS.name,
        "commissioning_distro_series": DEFAULT_OS.get_default_commissioning_release(),
        "default_dns_ttl": 30,
        "default_min_hwe_kernel": "",
        "default_storage_layout": "flat",
        # kernel options
        "kernel_opts": None,
        # Network section configuration.
        "maas_url": "http://localhost:5240/MAAS",
        "maas_name": gethostname(),
        "theme": "",
        "default_osystem": DEFAULT_OS.name,
        "default_distro_series": DEFAULT_OS.get_default_release(),
        # Proxy settings
        "enable_http_proxy": True,
        "maas_proxy_port": 8000,
        "use_peer_proxy": False,
        "http_proxy": None,
        "prefer_v4_proxy": False,
        # DNS settings
        "upstream_dns": None,
        "dnssec_validation": "auto",
        "dns_trusted_acl": None,
        "maas_internal_domain": "maas-internal",
        # NTP settings
        "ntp_servers": "ntp.ubuntu.com",
        "ntp_external_only": False,
        "omapi_key": "",
        # Syslog settings
        "remote_syslog": None,
        "maas_syslog_port": 5247,
        # Network discovery.
        "network_discovery": "enabled",
        "active_discovery_interval": _timedelta_to_whole_seconds(hours=3),
        "active_discovery_last_scan": 0,
        # RPC configuration.
        "rpc_shared_secret": None,
        "uuid": None,
        # Images.
        "boot_images_auto_import": True,
        "boot_images_no_proxy": False,
        # Third Party
        "enable_third_party_drivers": True,
        # Disk erasing.
        "enable_disk_erasing_on_release": False,
        "disk_erase_with_secure_erase": True,
        "disk_erase_with_quick_erase": False,
        # Curtin.
        "curtin_verbose": True,
        # Netplan
        "force_v1_network_yaml": False,
        # Analytics.
        "enable_analytics": True,
        # First admin journey.
        "completed_intro": False,
        "max_node_commissioning_results": 10,
        "max_node_testing_results": 10,
        "max_node_installation_results": 3,
        # Notifications.
        "subnet_ip_exhaustion_threshold_count": 16,
        "release_notifications": True,
        # MAAS Architecture.
        "use_rack_proxy": True,
        "node_timeout": 30,
        # prometheus.
        "prometheus_enabled": False,
        "prometheus_push_gateway": None,
        "prometheus_push_interval": 60,
        # Loki Promtail
        "promtail_enabled": False,
        "promtail_port": 5238,
        # Enlistment options
        "enlist_commissioning": True,
        "maas_auto_ipmi_user": "maas",
        "maas_auto_ipmi_user_privilege_level": "ADMIN",
        "maas_auto_ipmi_k_g_bmc_key": "",
        "maas_auto_ipmi_cipher_suite_id": "3",
        "maas_auto_ipmi_workaround_flags": None,
        # VMware vCenter crednetials
        "vcenter_server": "",
        "vcenter_username": "",
        "vcenter_password": "",
        "vcenter_datacenter": "",
        # Hardware Sync options
        "hardware_sync_interval": "15m",
        # TLS certificate options
        "tls_port": None,
        "tls_cert_expiration_notification_enabled": False,
        "tls_cert_expiration_notification_interval": 30,
        "vault_enabled": False,
        # Windows settings
        "windows_kms_host": None,
        "auto_vlan_creation": True,
    }


# Default values for config options.
DEFAULT_CONFIG = get_default_config()

# Map config keys that are secrets to their path in the Secret model (as
# they're actually stored there)
CONFIG_SECRETS = {
    "rpc_shared_secret": "rpc-shared",
    "omapi_key": "omapi-key",
    "maas_auto_ipmi_k_g_bmc_key": "ipmi-k_g-key",
    "vcenter_password": "vcenter-password",
}

# Encapsulates the possible states for network discovery
NetworkDiscoveryConfig = namedtuple(
    "NetworkDiscoveryConfig", ("active", "passive")
)


class ConfigManager(Manager):
    """Manager for Config model class.

    Don't import or instantiate this directly; access as `Config.objects`.
    """

    def __init__(self):
        super().__init__()
        self._config_changed_connections = defaultdict(set)

    def get_config(self, name, default=None):
        """Return the config value corresponding to the given config name.
        Return None or the provided default if the config value does not
        exist.

        :param name: The name of the config item.
        :type name: unicode
        :param default: The optional default value to return if no such config
            item exists.
        :type default: object
        :return: A config value.
        :raises: Config.MultipleObjectsReturned
        """
        from maasserver.secrets import SecretManager, SecretNotFound

        secret_name = CONFIG_SECRETS.get(name)
        try:
            if secret_name:
                return SecretManager().get_simple_secret(secret_name)
            return self.get(name=name).value
        except (Config.DoesNotExist, SecretNotFound):
            return copy.deepcopy(DEFAULT_CONFIG.get(name, default))

    def get_configs(self, names):
        """Return the config values corresponding to the given config names.
        Return None or the provided default if the config value does not
        exist.
        """
        from maasserver.secrets import SecretManager, SecretNotFound

        # set defaults
        configs = {
            key: copy.deepcopy(value)
            for key, value in get_default_config().items()
            if key in names
        }

        # secrets configs
        secret_manager = SecretManager()
        regular_configs = []
        for name in names:
            secret_name = CONFIG_SECRETS.get(name)
            if secret_name:
                with suppress(SecretNotFound):
                    configs[name] = secret_manager.get_simple_secret(
                        secret_name
                    )
            else:
                regular_configs.append(name)

        # other configs
        configs.update(
            self.filter(name__in=regular_configs).values_list("name", "value")
        )
        return configs

    def set_config(self, name, value, endpoint=None, request=None):
        """Set or overwrite a config value.

        :param name: The name of the config item to set.
        :type name: unicode
        :param value: The value of the config item to set.
        :type value: Any jsonizable object
        :param endpoint: The endpoint of the audit event to be created.
        :type endpoint: Integer enumeration of ENDPOINT.
        :param request: The http request of the audit event to be created.
        :type request: HttpRequest object.
        """
        from maasserver.audit import create_audit_event
        from maasserver.secrets import SecretManager

        secret_name = CONFIG_SECRETS.get(name)
        if secret_name:
            SecretManager().set_simple_secret(secret_name, value)
        else:
            self.update_or_create(name=name, defaults={"value": value})
        notify_action("config", "update", name)
        if endpoint is not None and request is not None:
            create_audit_event(
                EVENT_TYPES.SETTINGS,
                endpoint,
                request,
                None,
                description=(
                    f"Updated configuration setting '{name}' to '{value}'."
                ),
            )

    def config_changed_connect(self, config_name, method):
        """Connect a method to Django's 'update' signal for given config name.

        :param config_name: The name of the config item to track.
        :type config_name: unicode
        :param method: The method to be called.
        :type method: callable

        The provided callable should follow Django's convention.  E.g::

          >>> def callable(sender, instance, created, **kwargs):
          ...     pass

          >>> Config.objects.config_changed_connect('config_name', callable)

        """
        self._config_changed_connections[config_name].add(method)

    def config_changed_disconnect(self, config_name, method):
        """Disconnect from Django's 'update' signal for given config name.

        :param config_name: The name of the config item.
        :type config_name: unicode
        :param method: The method to be removed.
        :type method: callable
        """
        self._config_changed_connections[config_name].discard(method)

    def _config_changed(self, sender, instance, created, **kwargs):
        for connection in self._config_changed_connections[instance.name]:
            connection(sender, instance, created, **kwargs)

    def get_network_discovery_config_from_value(self, value):
        """Given the configuration value for `network_discovery`, return
        a `namedtuple` (`NetworkDiscoveryConfig`) of booleans: (active,
        passive).
        """
        discovery_mode = value
        active = discovery_mode == "active"
        passive = active or (discovery_mode == "enabled")
        return NetworkDiscoveryConfig(active, passive)

    def get_network_discovery_config(self):
        return self.get_network_discovery_config_from_value(
            self.get_config("network_discovery")
        )


class Config(Model):
    """Configuration settings item.

    :ivar name: The name of the configuration option.
    :type name: unicode
    :ivar value: The configuration value.
    :type value: Any pickleable python object.
    """

    name = CharField(max_length=255, unique=True)
    value = JSONObjectField(null=True)

    objects = ConfigManager()

    def __str__(self):
        return f"{self.name}: {self.value}"


def ensure_uuid_in_config() -> str:
    """Return the UUID for this MAAS cluster (creating it if necessary)."""
    maas_uuid = Config.objects.get_config("uuid")
    if maas_uuid is None:
        maas_uuid = str(uuid.uuid4())
        Config.objects.set_config("uuid", maas_uuid)
    return maas_uuid


# Connect config manager's _config_changed to Config's post-save signal.
post_save.connect(Config.objects._config_changed, sender=Config)
