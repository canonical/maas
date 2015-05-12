# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Hardware Drivers."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "Architecture",
    "ArchitectureRegistry",
    "BootResource",
    ]

from abc import (
    ABCMeta,
    abstractmethod,
)

from jsonschema import validate
from provisioningserver.power_schema import JSON_POWER_TYPE_PARAMETERS
from provisioningserver.utils.registry import Registry

# JSON schema representing the Django choices format as JSON; an array of
# 2-item arrays.
CHOICE_FIELD_SCHEMA = {
    'type': 'array',
    'items': {
        'title': "Setting parameter field choice",
        'type': 'array',
        'minItems': 2,
        'maxItems': 2,
        'uniqueItems': True,
        'items': {
            'type': 'string',
        }
    },
}

# JSON schema for what a settings field should look like.
SETTING_PARAMETER_FIELD_SCHEMA = {
    'title': "Setting parameter field",
    'type': 'object',
    'properties': {
        'name': {
            'type': 'string',
        },
        'field_type': {
            'type': 'string',
        },
        'label': {
            'type': 'string',
        },
        'required': {
            'type': 'boolean',
        },
        'choices': CHOICE_FIELD_SCHEMA,
        'default': {
            'type': 'string',
        },
    },
    'required': ['field_type', 'label', 'required'],
}


# JSON schema for what group of setting parameters should look like.
JSON_SETTING_SCHEMA = {
    'title': "Setting parameters set",
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
    },
    'required': ['name', 'description', 'fields'],
}


def make_setting_field(
        name, label, field_type=None, choices=None, default=None,
        required=False):
    """Helper function for building a JSON setting parameters field.

    :param name: The name of the field.
    :type name: string
    :param label: The label to be presented to the user for this field.
    :type label: string
    :param field_type: The type of field to create. Can be one of
        (string, choice, mac_address). Defaults to string.
    :type field_type: string.
    :param choices: The collection of choices to present to the user.
        Needs to be structured as a list of lists, otherwise
        make_setting_field() will raise a ValidationError.
    :type list:
    :param default: The default value for the field.
    :type default: string
    :param required: Whether or not a value for the field is required.
    :type required: boolean
    """
    if field_type not in ('string', 'mac_address', 'choice'):
        field_type = 'string'
    if choices is None:
        choices = []
    validate(choices, CHOICE_FIELD_SCHEMA)
    if default is None:
        default = ""
    field = {
        'name': name,
        'label': label,
        'required': required,
        'field_type': field_type,
        'choices': choices,
        'default': default,
    }
    return field


def validate_settings(setting_fields):
    """Helper that validates that the fields adhere to the JSON schema."""
    validate(setting_fields, JSON_SETTING_SCHEMA)


class Architecture:

    def __init__(self, name, description, pxealiases=None,
                 kernel_options=None):
        """Represents an architecture in the driver context.

        :param name: The architecture name as used in MAAS.
            arch/subarch or just arch.
        :param description: The human-readable description for the
            architecture.
        :param pxealiases: The optional list of names used if the
            hardware uses a different name when requesting its bootloader.
        :param kernel_options: The optional list of kernel options for this
            architecture.  Anything supplied here supplements the options
            provided by MAAS core.
        """
        if pxealiases is None:
            pxealiases = ()
        self.name = name
        self.description = description
        self.pxealiases = pxealiases
        self.kernel_options = kernel_options


class BootResource:
    """Abstraction of ephemerals and pxe resources required for a hardware
    driver.

    This resource is responsible for importing and reporting on
    what is potentially available in relation to a cluster controller.
    """

    __metaclass__ = ABCMeta

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def import_resources(self, at_location, filter=None):
        """Import the specified resources.

        :param at_location: URL to a Simplestreams index or a local path
            to a directory containing boot resources.
        :param filter: A simplestreams filter.
            e.g. "release=trusty label=beta-2 arch=amd64"
            This is ignored if the location is a local path, all resources
            at the location will be imported.
        TBD: How to provide progress information.
        """

    @abstractmethod
    def describe_resources(self, at_location):
        """Enumerate all the boot resources.

        :param at_location: URL to a Simplestreams index or a local path
            to a directory containing boot resources.

        :return: a list of dictionaries describing the available resources,
            which will need to be imported so the driver can use them.
        [
            {
                "release": "trusty",
                "arch": "amd64",
                "label": "beta-2",
                "size": 12344556,
            }
            ,
        ]
        """


class HardwareDiscoverContext:

    __metaclass__ = ABCMeta

    @abstractmethod
    def startDiscovery(self):
        """TBD"""

    @abstractmethod
    def stopDiscovery(self):
        """TBD"""


class ArchitectureRegistry(Registry):
    """Registry for architecture classes."""

    @classmethod
    def get_by_pxealias(cls, alias):
        for _, arch in cls:
            if alias in arch.pxealiases:
                return arch
        return None


class BootResourceRegistry(Registry):
    """Registry for boot resource classes."""


class PowerTypeRegistry(Registry):
    """Registry for power type classes."""


builtin_architectures = [
    Architecture(name="i386/generic", description="i386"),
    Architecture(name="amd64/generic", description="amd64"),
    Architecture(
        name="arm64/generic", description="arm64/generic",
        pxealiases=["arm"]),
    Architecture(
        name="arm64/xgene-uboot", description="arm64/xgene-uboot",
        pxealiases=["arm"]),
    Architecture(
        name="arm64/xgene-uboot-mustang",
        description="arm64/xgene-uboot-mustang", pxealiases=["arm"]),
    Architecture(
        name="armhf/highbank", description="armhf/highbank",
        pxealiases=["arm"], kernel_options=["console=ttyAMA0"]),
    Architecture(
        name="armhf/generic", description="armhf/generic",
        pxealiases=["arm"], kernel_options=["console=ttyAMA0"]),
    Architecture(
        name="armhf/keystone", description="armhf/keystone",
        pxealiases=["arm"]),
    # PPC64EL needs a rootdelay for PowerNV. The disk controller
    # in the hardware, takes a little bit longer to come up then
    # the initrd wants to wait. Set this to 60 seconds, just to
    # give the booting machine enough time. This doesn't slow down
    # the booting process, it just increases the timeout.
    Architecture(
        name="ppc64el/generic", description="ppc64el",
        kernel_options=['rootdelay=60']),
]
for arch in builtin_architectures:
    ArchitectureRegistry.register_item(arch.name, arch)


builtin_power_types = JSON_POWER_TYPE_PARAMETERS
for power_type in builtin_power_types:
    PowerTypeRegistry.register_item(power_type['name'], power_type)
