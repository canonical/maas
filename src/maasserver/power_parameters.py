# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Power parameters.  Each possible value of a Node's power_type field can
be associated with specific 'power parameters' wich will be used when
powering up or down the node in question.  These 'power parameters' will be
stored as a JSON object in the Node's power parameter field.  Even if we want
to allow arbitrary power parameters to be set using the API for maximum
flexibility, each value of power type is associated with a set of 'sensible'
power parameters.  That is used to validate data (but again, it is possible
to bypass that validation step and store arbitrary power parameters) and by
the UI to display the right power parameter fields that correspond to the
selected power_type.  The classes in this module are used to associate each
power type with a set of power parameters.

To define a new set of power parameters for a new power_type: create a new
mapping between the new power type and a DictCharField instance in
`POWER_TYPE_PARAMETERS`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'POWER_TYPE_PARAMETERS',
    ]


from django import forms
from jsonschema import validate
from maasserver.config_forms import DictCharField
from maasserver.fields import MACAddressFormField
from provisioningserver.enum import (
    IPMI_DRIVER,
    IPMI_DRIVER_CHOICES,
    )


# Represent the Django choices format as JSON; an array of 2-item
# arrays.
CHOICE_FIELD_SCHEMA = {
    'type': 'array',
    'items': {
        'title': "Power type paramter field choice",
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
JSON_POWER_TYPE_PARAMETERS_SCHEMA = {
    'title': "Power parameters set",
    'type': 'array',
    'items': {
        'title': "Power type parameters",
        'type': 'object',
        'properties': {
            'fields': {
                'type': 'array',
                'items': POWER_TYPE_PARAMETER_FIELD_SCHEMA,
            },
        },
        'required': ['fields'],
    },
}


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


# FIXME this should all be produced by hardware drivers, not defined statically
# like this.
JSON_POWER_TYPE_PARAMETERS = [
    {
        'name': 'ether_wake',
        'fields': [
            make_json_field(
                'mac_address', "MAC Address", field_type='mac_address'),
        ],
    },
    {
        'name': 'virsh',
        'fields': [
            make_json_field('power_address', "Power address"),
            make_json_field('power_id', "Power ID"),
        ],
    },
    {
        'name': 'fence_cdu',
        'fields': [
            make_json_field('power_address', "Power address"),
            make_json_field('power_id', "Power ID"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
        ],
    },
    {
        'name': 'ipmi',
        'fields': [
            make_json_field(
                'power_driver', "Power driver", field_type='choice',
                choices=IPMI_DRIVER_CHOICES, default=IPMI_DRIVER.LAN_2_0),
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
        ],
    },
    {
        'name': 'moonshot',
        'fields': [
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
            make_json_field('power_hwaddress', "Power hardware address"),
        ],
    },
    {
        'name': 'sm15k',
        'fields': [
            make_json_field('system_id', "System ID"),
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
        ],
    },
    {
        'name': 'amt',
        'fields': [
            make_json_field(
                'mac_address', "MAC Address", field_type='mac_address'),
            make_json_field('power_pass', "Power password"),
        ],
    },
    {
        'name': 'dli',
        'fields': [
            make_json_field('system_id', "Outlet ID"),
            make_json_field('power_address', "Power address"),
            make_json_field('power_user', "Power user"),
            make_json_field('power_pass', "Power password"),
        ],
    },
]


FIELD_TYPE_MAPPINGS = {
    'string': forms.CharField,
    'mac_address': MACAddressFormField,
    'choice': forms.ChoiceField,
}


def make_form_field(json_field):
    """Build a Django form field based on the JSON spec.

    :param json_field: The JSON-specified field to convert into a valid
        Djangoism.
    :type json_field: dict
    :return: The correct Django form field for the field type, as
        specified in FIELD_TYPE_MAPPINGS.
    """
    field_class = FIELD_TYPE_MAPPINGS.get(
        json_field['field_type'], forms.CharField)
    if json_field['field_type'] == 'choice':
        extra_parameters = {
            'choices': json_field['choices'],
            'initial': json_field['default'],
            }
    else:
        extra_parameters = {}
    form_field = field_class(
        label=json_field['label'], required=json_field['required'],
        **extra_parameters)
    return form_field


def get_power_type_parameters_from_json(json_power_type_parameters):
    """Return power type parameters.

    :param json_power_type_parameters: Power type parameters expressed
        as a JSON string or as set of JSONSchema-verifiable objects.
        Will be validated using jsonschema.validate().
    :type json_power_type_parameters: JSON string or iterable.
    :return: A dict of power parameters for all power types, indexed by
        power type name.
    """
    validate(json_power_type_parameters, JSON_POWER_TYPE_PARAMETERS_SCHEMA)
    power_parameters = {
        # Empty type, for the case where nothing is entered in the form yet.
        '': DictCharField(
            [], required=False, skip_check=True),
    }
    for power_type in json_power_type_parameters:
        fields = []
        for json_field in power_type['fields']:
            fields.append((
                json_field['name'], make_form_field(json_field)))
        params = DictCharField(fields, required=False, skip_check=True)
        power_parameters[power_type['name']] = params
    return power_parameters


# We do this once because there's no point re-parsing the JSON every
# time we need to look up the power type parameters code.
POWER_TYPE_PARAMETERS = get_power_type_parameters_from_json(
    JSON_POWER_TYPE_PARAMETERS)
