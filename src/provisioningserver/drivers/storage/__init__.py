# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Base storage driver."""

__all__ = [
    "StorageActionError",
    "StorageAuthError",
    "StorageConnError",
    "StorageDriver",
    "StorageError",
    "StorageFatalError",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
    abstractproperty,
)

import attr
from jsonschema import validate
from provisioningserver.drivers import (
    AttrHelperMixin,
    convert_list,
    convert_obj,
    IP_EXTRACTOR_SCHEMA,
    SETTING_PARAMETER_FIELD_SCHEMA,
    SETTING_SCOPE,
)

# JSON schema for what a storage driver definition should look like.
JSON_STORAGE_DRIVER_SCHEMA = {
    'title': "Storage driver setting set",
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
        },
        'description': {
            'type': 'string',
        },
        'fields': {
            'type': 'array',
            'items': SETTING_PARAMETER_FIELD_SCHEMA,
        },
        'ip_extractor': IP_EXTRACTOR_SCHEMA,
        'missing_packages': {
            'type': 'array',
            'items': {
                'type': 'string',
            },
        },
        'pod_driver': {
            'type': 'string',
        },
    },
    'required': [
        'name', 'description', 'fields'],
}

# JSON schema for multple storage drivers.
JSON_STORAGE_DRIVERS_SCHEMA = {
    'title': "Storage drivers parameters set",
    'type': 'array',
    'items': JSON_STORAGE_DRIVER_SCHEMA,
}


class StorageError(Exception):
    """Base error for all stroge driver failure commands."""


class StorageFatalError(StorageError):
    """Error that is raised when the storage action should not continue to
    retry at all.

    This exception will cause the storage action to fail instantly,
    without retrying.
    """


class StorageAuthError(StorageFatalError):
    """Error raised when storage driver fails to authenticate to the
    storage system.

    This exception will cause the pod action to fail instantly,
    without retrying.
    """


class StorageConnError(StorageError):
    """Error raised when storage driver fails to communicate to the stroage
    system."""


class StorageActionError(StorageError):
    """Error when actually performing an action on the storage system, like
    `create` or `delete`."""


@attr.s
class DiscoveredVolume(AttrHelperMixin):
    """Discovered storage volume."""
    size = attr.ib(convert=int)
    block_size = attr.ib(convert=int, default=512)
    tags = attr.ib(convert=convert_list(str), default=[])


@attr.s
class DiscoveredStorage(AttrHelperMixin):
    """Discovered storage information."""
    size = attr.ib(convert=int)
    volumes = attr.ib(
        convert=convert_list(DiscoveredVolume), default=[])
    parameters = attr.ib(convert=convert_obj(dict), default={})

    # When a Pod discovers storage it sets the driver_type so MAAS knows
    # which storage driver to call to perform the action. When a storage
    # driver has `discover` call this is not required to be set, as MAAS
    # already knows the driver.
    driver_type = attr.ib(
        convert=convert_obj(str, optional=True), default=None)


@attr.s
class RequestedVolume(AttrHelperMixin):
    """Requested storage volume information."""
    size = attr.ib(convert=int)


class StorageDriver(metaclass=ABCMeta):
    """Base driver for a storage driver."""

    # Optional Pod driver that this storage driver is related to.
    # When a storage driver defines a Pod driver then it will recieve the
    # parameters from the Pod driver in the passed context along with the
    # defined settings for the storage system.
    pod_driver = None

    def __init__(self):
        super(StorageDriver, self).__init__()
        validate(
            self.get_schema(detect_missing_packages=False),
            JSON_STORAGE_DRIVER_SCHEMA)
        # Ensure that the settings defined on the driver are only storage
        # based settings.
        for setting in self.settings:
            if setting['scope'] != SETTING_SCOPE.STORAGE:
                raise ValueError(
                    "Storage driver '%s' has invalid setting '%s': '%s' is "
                    "not allowed on a storage driver, only '%s' is "
                    "allowed." % (
                        self.name, setting['name'],
                        setting['scope'], SETTING_SCOPE.STORAGE))

    @abstractproperty
    def name(self):
        """Name of the storage driver."""

    @abstractproperty
    def description(self):
        """Description of the storage driver."""

    @abstractproperty
    def settings(self):
        """List of settings for the driver.

        Each setting in this list will be different per user. They are passed
        to the `discover`, `create_volume`, and `delete_volume` using the
        context. It is up to the driver to read these options before
        performing the operation.
        """

    @abstractproperty
    def ip_extractor(self):
        """IP extractor.

        Name of the settings field and python REGEX pattern for extracting IP
        the address from the value.
        """

    @abstractmethod
    def detect_missing_packages(self):
        """Implement this method for the actual implementation
        of the check for the driver's missing support packages.
        """

    @abstractmethod
    def discover(self, context, storage_id=None):
        """Discover the storage resources.

        :param context: Storage settings.
        :param storage_id: Storage id.
        :returns: `Deferred` returning `DiscoveredStorage`.
        :rtype: `twisted.internet.defer.Deferred`
        """

    @abstractmethod
    def create_volume(self, storage_id, context, request):
        """Create a storage volume.

        :param storage_id: Storage id.
        :param context: Storage settings.
        :param request: Requested volume.
        :type request: `RequestedVolume`.
        :returns: `DiscoveredVolume`.
        """

    @abstractmethod
    def delete_volume(self, storage_id, context, request):
        """Delete a storage volume.

        :param storage_id: Storage id.
        :param context: Storage settings.
        :param request: Requested volume to delete.
        :type request: `DiscoveredVolume`.
        """

    def get_schema(self, detect_missing_packages=True):
        """Returns the JSON schema for the driver.

        Calculates the missing packages on each invoke.
        """
        schema = dict(
            name=self.name, description=self.description, fields=self.settings,
            missing_packages=(
                self.detect_missing_packages()
                if detect_missing_packages else []))
        if self.ip_extractor is not None:
            schema['ip_extractor'] = self.ip_extractor
        if self.pod_driver is not None:
            schema['pod_driver'] = '%s' % self.pod_driver.name
        return schema

    def get_setting(self, name):
        """Return the setting field by its name."""
        for setting in self.settings:
            if setting['name'] == name:
                return setting
        return None


def get_error_message(err):
    """Returns the proper error message based on error."""
    if isinstance(err, StorageAuthError):
        return "Could not authenticate to storage system: %s" % err
    elif isinstance(err, StorageConnError):
        return "Could not contact storage system: %s" % err
    elif isinstance(err, StorageActionError):
        return "Failed to complete storage action: %s" % err
    else:
        return "Failed talking to storage system: %s" % err
