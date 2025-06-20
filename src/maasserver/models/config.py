# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items."""

from collections import namedtuple
import uuid

from django.db.models import CharField, JSONField, Manager, Model

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.listener import notify_action
from maasserver.sqlalchemy import service_layer
from maasserver.utils.orm import post_commit_do
from maasserver.workflow import start_workflow
from maasservicelayer.models.configurations import ActiveDiscoveryIntervalEnum
from provisioningserver.events import EVENT_TYPES
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()

DNSSEC_VALIDATION_CHOICES = [
    ("auto", "Automatic (use default root key)"),
    ("yes", "Yes (manually configured root key)"),
    ("no", "No (Disable DNSSEC; useful when upstream DNS is misconfigured)"),
]

NETWORK_DISCOVERY_CHOICES = [("enabled", "Enabled"), ("disabled", "Disabled")]

ACTIVE_DISCOVERY_INTERVAL_CHOICES = [
    (ActiveDiscoveryIntervalEnum.NEVER.value, "Never (disabled)"),
    (ActiveDiscoveryIntervalEnum.EVERY_WEEK.value, "Every week"),
    (ActiveDiscoveryIntervalEnum.EVERY_DAY.value, "Every day"),
    (ActiveDiscoveryIntervalEnum.EVERY_12_HOURS.value, "Every 12 hours"),
    (ActiveDiscoveryIntervalEnum.EVERY_6_HOURS.value, "Every 6 hours"),
    (ActiveDiscoveryIntervalEnum.EVERY_3_HOURS.value, "Every 3 hours"),
    (ActiveDiscoveryIntervalEnum.EVERY_HOUR.value, "Every hour"),
    (ActiveDiscoveryIntervalEnum.EVERY_30_MINUTES.value, "Every 30 minutes"),
    (ActiveDiscoveryIntervalEnum.EVERY_10_MINUTES.value, "Every 10 minutes"),
]

# Encapsulates the possible states for network discovery
NetworkDiscoveryConfig = namedtuple(
    "NetworkDiscoveryConfig", ("active", "passive")
)


class ConfigManager(Manager):
    """Manager for Config model class.

    Don't import or instantiate this directly; access as `Config.objects`.
    """

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
        """
        return service_layer.services.configurations.get(name, default)

    def get_configs(self, names):
        """Return the config values corresponding to the given config names.
        Return None or the provided default if the config value does not
        exist.
        """
        return service_layer.services.configurations.get_many(names)

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

        service_layer.services.configurations.set(name, value)

        self._handle_config_value_changed(name, value)
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

    def _handle_ntp_servers_config(self):
        from maasserver.models.vlan import VLAN

        vlan_ids = [vlan.id for vlan in VLAN.objects.filter(dhcp_on=True)]

        if vlan_ids:
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(
                    vlan_ids=vlan_ids,
                ),
                task_queue="region",
            )

    def _handle_config_value_changed(self, name, value):
        """Hook handlers for changes in specific config parameters."""
        from maasserver.bootsources import update_boot_source_cache
        from maasserver.interface import update_interface_monitoring
        from maasserver.models.domain import dns_kms_setting_changed
        from maasserver.sessiontimeout import clear_existing_sessions

        handlers = {
            "enable_http_proxy": lambda _name,
            _value: update_boot_source_cache(),
            "http_proxy": lambda _name, _value: update_boot_source_cache(),
            "network_discovery": lambda _name,
            _value: update_interface_monitoring(_value),
            "ntp_external_only": lambda _name,
            _value: self._handle_ntp_servers_config(),
            "ntp_servers": lambda _name,
            _value: self._handle_ntp_servers_config(),
            "session_length": lambda _name, _value: clear_existing_sessions(),
            "windows_kms_host": lambda _name,
            _value: dns_kms_setting_changed(),
        }

        handler = handlers.get(name)
        if handler:
            handler(name, value)


class Config(Model):
    """Configuration settings item.

    :ivar name: The name of the configuration option.
    :type name: unicode
    :ivar value: The configuration value.
    :type value: Any pickleable python object.
    """

    name = CharField(max_length=255, unique=True)
    value = JSONField(null=True)

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
