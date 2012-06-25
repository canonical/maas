# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Configuration items."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'Config',
    ]


from collections import defaultdict
import copy
from socket import gethostname

from django.conf import settings
from django.db.models import (
    CharField,
    Manager,
    Model,
    )
from django.db.models.signals import post_save
from maasserver import DefaultMeta
from maasserver.enum import NODE_AFTER_COMMISSIONING_ACTION
from maasserver.fields import JSONObjectField
from provisioningserver.enum import POWER_TYPE


def get_default_config():
    return {
        ## settings default values.
        # Commissioning section configuration.
        'after_commissioning': NODE_AFTER_COMMISSIONING_ACTION.DEFAULT,
        'check_compatibility': False,
        'node_power_type': POWER_TYPE.WAKE_ON_LAN,
        # The host name or address where the nodes can access the metadata
        # service of this MAAS.
        'maas_url': settings.DEFAULT_MAAS_URL,
        # Ubuntu section configuration.
        'fallback_master_archive': False,
        'keep_mirror_list_uptodate': False,
        'fetch_new_releases': False,
        'update_from': 'archive.ubuntu.com',
        'update_from_choice': (
            [['archive.ubuntu.com', 'archive.ubuntu.com']]),
        # Network section configuration.
        'maas_name': gethostname(),
        'enlistment_domain': b'local',
        ## /settings
        }


# Default values for config options.
DEFAULT_CONFIG = get_default_config()


class ConfigManager(Manager):
    """Manager for Config model class.

    Don't import or instantiate this directly; access as `Config.objects.
    """

    def __init__(self):
        super(ConfigManager, self).__init__()
        self._config_changed_connections = defaultdict(set)

    def get_config(self, name, default=None):
        """Return the config value corresponding to the given config name.
        Return None or the provided default if the config value does not
        exist.

        :param name: The name of the config item.
        :type name: basestring
        :param name: The optional default value to return if no such config
            item exists.
        :type name: object
        :return: A config value.
        :raises: Config.MultipleObjectsReturned
        """
        try:
            return self.get(name=name).value
        except Config.DoesNotExist:
            return copy.deepcopy(DEFAULT_CONFIG.get(name, default))

    def get_config_list(self, name):
        """Return the config value list corresponding to the given config
        name.

        :param name: The name of the config items.
        :type name: basestring
        :return: A list of the config values.
        :rtype: list
        """
        return [config.value for config in self.filter(name=name)]

    def set_config(self, name, value):
        """Set or overwrite a config value.

        :param name: The name of the config item to set.
        :type name: basestring
        :param value: The value of the config item to set.
        :type value: Any jsonizable object
        """
        try:
            existing = self.get(name=name)
            existing.value = value
            existing.save()
        except Config.DoesNotExist:
            self.create(name=name, value=value)

    def config_changed_connect(self, config_name, method):
        """Connect a method to Django's 'update' signal for given config name.

        :param config_name: The name of the config item to track.
        :type config_name: basestring
        :param method: The method to be called.
        :type method: callable

        The provided callabe should follow Django's convention.  E.g:

        >>> def callable(sender, instance, created, **kwargs):
        >>>     pass
        >>>
        >>> Config.objects.config_changed_connect('config_name', callable)
        """
        self._config_changed_connections[config_name].add(method)

    def _config_changed(self, sender, instance, created, **kwargs):
        for connection in self._config_changed_connections[instance.name]:
            connection(sender, instance, created, **kwargs)


class Config(Model):
    """Configuration settings item.

    :ivar name: The name of the configuration option.
    :type name: basestring
    :ivar value: The configuration value.
    :type value: Any pickleable python object.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    name = CharField(max_length=255, unique=False)
    value = JSONObjectField(null=True)

    objects = ConfigManager()

    def __unicode__(self):
        return "%s: %s" % (self.name, self.value)


# Connect config manager's _config_changed to Config's post-save signal.
post_save.connect(Config.objects._config_changed, sender=Config)
