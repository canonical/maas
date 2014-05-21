# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Define json schema for power parameters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "JSON_POWER_TYPE_PARAMETERS",
    "JSON_POWER_TYPE_SCHEMA",
    "POWER_TYPE_PARAMETER_FIELD_SCHEMA",
    ]


from jsonschema import validate

# We specifically declare this here so that a node not knowing its own
# powertype won't fail to enlist. However, we don't want it in the list
# of power types since setting a node's power type to "I don't know"
# from another type doens't make any sense.
UNKNOWN_POWER_TYPE = ''


class IPMI_DRIVER:
    DEFAULT = ''
    LAN = 'LAN'
    LAN_2_0 = 'LAN_2_0'


IPMI_DRIVER_CHOICES = [
    [IPMI_DRIVER.LAN, "LAN [IPMI 1.5]"],
    [IPMI_DRIVER.LAN_2_0, "LAN_2_0 [IPMI 2.0]"],
    ]


# Represent the Django choices format as JSON; an array of 2-item
# arrays.
CHOICE_FIELD_SCHEMA = {
    'type': 'array',
    'items': {
        'title': "Power type parameter field choice",
        'type': 'array',
        'minItems': 2,
        'maxItems': 2,
        'uniqueItems': True,
        'items': {
            'type': 'string',
        }
    },
}


POWER_TYPE_PARAMETER_FIELD_SCHEMA = {
    'title': "Power type parameter field",
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


# A basic JSON schema for what power type parameters should look like.
JSON_POWER_TYPE_SCHEMA = {
    'title': "Power parameters set",
    'type': 'array',
    'items': {
        'title': "Power type parameters",
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
                'items': POWER_TYPE_PARAMETER_FIELD_SCHEMA,
            },
        },
        'required': ['name', 'description', 'fields'],
    },
}


# Power control choices for sm15k power type
SM15K_POWER_CONTROL_CHOICES = [
    ["ipmi", "IPMI"],
    ["restapi", "REST API v0.9"],
    ["restapi2", "REST API v2.0"],
    ]


def make_json_field(
        name, label, field_type=None, choices=None, default=None,
        required=False):
    """Helper function for building a JSON power type parameters field.

    :param name: The name of the field.
    :type name: string
    :param label: The label to be presented to the user for this field.
    :type label: string
    :param field_type: The type of field to create. Can be one of
        (string, choice, mac_address). Defaults to string.
    :type field_type: string.
    :param choices: The collection of choices to present to the user.
        Needs to be structured as a list of lists, otherwise
        make_json_field() will raise a ValidationError.
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


JSON_POWER_TYPE_PARAMETERS = [
    {
        'name': 'ether_wake',
        'description': 'Wake-on-LAN',
        'fields': [
            make_json_field(
                'mac_address', "MAC Address", field_type='mac_address'),
        ],
    },
    {
        'name': 'virsh',
        'description': 'Virsh (virtual systems)',
        'fields': [
            make_json_field('power_address', "Power address"),
            make_json_field('power_id', "Power ID"),
            make_json_field(
                'power_pass', "Power password (optional)",
                required=False),
        ],
    },
    {
        'name': 'fence_cdu',
        'description': 'Sentry Switch CDU',
        'fields': [
            make_json_field('power_address', "Power address"),
            make_json_field('power_id', "Power ID"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
        ],
    },
    {
        'name': 'ipmi',
        'description': 'IPMI',
        'fields': [
            make_json_field(
                'power_driver', "Power driver", field_type='choice',
                choices=IPMI_DRIVER_CHOICES, default=IPMI_DRIVER.LAN_2_0),
            make_json_field('power_address', "IP address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
            make_json_field(
                'mac_address',
                "MAC address - the IP is looked up with ARP and is used if "
                "IP address is empty. This is better when the BMC uses DHCP."),
        ],
    },
    {
        'name': 'moonshot',
        'description': 'iLO4 Moonshot Chassis',
        'fields': [
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
            make_json_field('power_hwaddress', "Power hardware address"),
        ],
    },
    {
        'name': 'sm15k',
        'description': 'SeaMicro 15000',
        'fields': [
            make_json_field('system_id', "System ID"),
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
            make_json_field(
                'power_control', "Power control type", field_type='choice',
                choices=SM15K_POWER_CONTROL_CHOICES, default='ipmi'),
        ],
    },
    {
        'name': 'amt',
        'description': 'Intel AMT',
        'fields': [
            make_json_field(
                'mac_address', "MAC Address", field_type='mac_address'),
            make_json_field('power_pass', "Power password"),
            make_json_field(
                'power_address',
                "An IP address to use instead of the node's primary NIC's IP "
                "(i.e. the IP of the MAC above, looked up with ARP)."),
        ],
    },
    {
        'name': 'dli',
        'description': 'Digital Loggers, Inc. PDU',
        'fields': [
            make_json_field('system_id', "Outlet ID"),
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
        ],
    },
    {
        'name': 'ucsm',
        'description': "Cisco UCS Manager",
        'fields': [
            make_json_field('uuid', "Server UUID"),
            make_json_field('power_address', "URL for XML API"),
            make_json_field('power_user', "API user"),
            make_json_field('power_pass', "API password"),
        ],
    },
]
