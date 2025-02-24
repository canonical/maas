# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items."""

from collections import defaultdict, namedtuple
from contextlib import suppress
import uuid

from django.db.models import CharField, JSONField, Manager, Model
from django.db.models.signals import post_save

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.listener import notify_action
from maasserver.utils.orm import post_commit_do
from maasserver.workflow import start_workflow
from maasservicelayer.models.configurations import (
    ActiveDiscoveryIntervalEnum,
    ConfigFactory,
)
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

        config_model = None
        try:
            config_model = ConfigFactory.get_config_model(name)
        except ValueError:
            log.warn(
                f"The configuration '{name}' is not known. Using the default {default} if the config does not exist in the DB."
            )
            default_value = default
        else:
            default_value = config_model.default
        try:
            if config_model and config_model.stored_as_secret:
                return SecretManager().get_simple_secret(
                    config_model.secret_name
                )
            return self.get(name=name).value
        except (Config.DoesNotExist, SecretNotFound):
            return default_value

    def get_configs(self, names):
        """Return the config values corresponding to the given config names.
        Return None or the provided default if the config value does not
        exist.
        """
        from maasserver.secrets import SecretManager, SecretNotFound

        config_models = {
            name: ConfigFactory.get_config_model(name)
            for name in names
            if name in ConfigFactory.ALL_CONFIGS
        }

        # Build a first result with all the default values, then look in the secrets/configs in the db for overrides.
        configs = {
            name: config_model.default
            for name, config_model in config_models.items()
        }

        # What configs we should lookup from the DB
        regular_configs = set(names)

        # secrets configs
        secret_manager = SecretManager()
        for name, model in config_models.items():
            if model.stored_as_secret:
                with suppress(SecretNotFound):
                    configs[name] = secret_manager.get_simple_secret(
                        model.secret_name
                    )
                    # The config was found and added to the result: remove it from the regular config.
                    regular_configs.remove(name)

        # Lookup the remaining configs from the DB.
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

        config_model = None
        try:
            config_model = ConfigFactory.get_config_model(name)
        except ValueError:
            log.warn(
                f"The configuration '{name}' is not known. Anyways, it's going to be stored in the DB."
            )
        if config_model and config_model.stored_as_secret:
            SecretManager().set_simple_secret(config_model.secret_name, value)
        else:
            self.update_or_create(name=name, defaults={"value": value})
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

    def _handle_config_value_changed(self, name, value):
        """Hook handlers for changes in specific config parameters."""
        from maasserver.sessiontimeout import clear_existing_sessions

        # XXX eventually we should move away from signals for performing tasks
        # on config changes, and call all handlers here.
        handlers = {
            "session_length": lambda _name, _value: clear_existing_sessions(),
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

    def save(self, *args, **kwargs):
        from maasserver.models.vlan import VLAN

        super().save(*args, **kwargs)
        if self.id and (
            self.name == "ntp_servers" or self.name == "ntp_external_only"
        ):
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
