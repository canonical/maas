# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
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
    'get_power_type_parameters',
    ]


from django import forms
from jsonschema import validate
from maasserver.config_forms import DictCharField
from maasserver.fields import MACAddressFormField
from provisioningserver.enum import get_power_types
from provisioningserver.power_schema import (
    JSON_POWER_TYPE_PARAMETERS,
    JSON_POWER_TYPE_PARAMETERS_SCHEMA,
    POWER_TYPE_PARAMETER_FIELD_SCHEMA,
    )


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


def add_power_type_parameters(
        name, fields, parameters_set=JSON_POWER_TYPE_PARAMETERS):
    """Add new power type parameters to JSON_POWER_TYPE_PARAMETERS.

    :param name: The name of the power type for which to add parameters.
    :type name: string
    :param fields: The fields that make up the parameters for the power
        type. Will be validated against
        POWER_TYPE_PARAMETER_FIELD_SCHEMA.
    :type field: list
    :param parameters_set: An existing list of power type parameters to
        mutate. By default, this is set to JSON_POWER_TYPE_PARAMETERS.
        This parameter exists for testing purposes.
    :type parameters_set: list
    """
    for power_type in parameters_set:
        if name == power_type['name']:
            return
    field_set_schema = {
        'title': "Power type parameters field set schema",
        'type': 'array',
        'items': POWER_TYPE_PARAMETER_FIELD_SCHEMA,
    }
    validate(fields, field_set_schema)
    parameters_set.append({'name': name, 'fields': fields})


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


# FIXME: This method uses JSON_POWER_TYPE_PARAMETERS.  It needs changing to
# query the cluster's information instead.
def get_power_type_parameters():
    return get_power_type_parameters_from_json(JSON_POWER_TYPE_PARAMETERS)


# FIXME: POWER_TYPE_PARAMETERS needs to go away;
# use get_power_type_parameters() instead because the power type information
# need to be generated on the fly to incude the latest information.
POWER_TYPE_PARAMETERS = get_power_type_parameters_from_json(
    JSON_POWER_TYPE_PARAMETERS)


def get_power_type_choices():
    return [(k, v) for (k, v) in get_power_types().items() if k != '']
