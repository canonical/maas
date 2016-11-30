# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
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

The power types are retrieved from the cluster controllers using the json
schema provisioningserver.drivers.power.JSON_POWER_DRIVERS_SCHEMA.  To add new
parameters requires changes to hardware drivers that run in the cluster
controllers.
"""

__all__ = [
    'get_all_power_types_from_clusters',
    'get_power_type_choices',
    'get_power_type_parameters',
    ]

from operator import itemgetter

from django import forms
from jsonschema import validate
from maasserver.clusterrpc.utils import call_clusters
from maasserver.config_forms import DictCharField
from maasserver.fields import MACAddressFormField
from maasserver.utils.forms import compose_invalid_choice_text
from provisioningserver.drivers import SETTING_PARAMETER_FIELD_SCHEMA
from provisioningserver.drivers.power import JSON_POWER_DRIVERS_SCHEMA
from provisioningserver.rpc import cluster


FIELD_TYPE_MAPPINGS = {
    'string': forms.CharField,
    'mac_address': MACAddressFormField,
    'choice': forms.ChoiceField,
    # This is used on the API so a password field is just a char field.
    'password': forms.CharField,
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
        invalid_choice_message = compose_invalid_choice_text(
            json_field['name'], json_field['choices'])
        extra_parameters = {
            'choices': json_field['choices'],
            'error_messages': {
                'invalid_choice': invalid_choice_message},
            }
    else:
        extra_parameters = {}

    default = json_field.get('default')
    if default is not None:
        extra_parameters['initial'] = default

    form_field = field_class(
        label=json_field['label'], required=json_field['required'],
        **extra_parameters)
    return form_field


def add_power_type_parameters(
        name, description, fields, missing_packages, parameters_set):
    """Add new power type parameters to the given parameters_set if it
    does not already exist.

    :param name: The name of the power type for which to add parameters.
    :type name: string
    :param description: A longer description of the power type. This
        will be displayed in the UI.
    :type description: string
    :param fields: The fields that make up the parameters for the power
        type. Will be validated against
        SETTING_PARAMETER_FIELD_SCHEMA.
    :param missing_packages: System packages that must be installed on
        the cluster before the power type can be used.
    :type fields: list of `make_setting_field` results.
    :param parameters_set: An existing list of power type parameters to
        mutate.
    :type parameters_set: list
    """
    for power_type in parameters_set:
        if name == power_type['name']:
            return
    field_set_schema = {
        'title': "Power type parameters field set schema",
        'type': 'array',
        'items': SETTING_PARAMETER_FIELD_SCHEMA,
    }
    validate(fields, field_set_schema)
    parameters_set.append(
        {'name': name, 'description': description, 'fields': fields,
         'missing_packages': missing_packages})


def get_power_type_parameters_from_json(
        json_power_type_parameters, initial_power_params=None,
        skip_check=False):
    """Return power type parameters.

    :param json_power_type_parameters: Power type parameters expressed
        as a JSON string or as set of JSONSchema-verifiable objects.
        Will be validated using jsonschema.validate().
    :type json_power_type_parameters: JSON string or iterable.
    :param initial_power_params: Power paramaters that were already set, any
        field which matches will have its initial value set.
    :type initial_power_params: dict
    :param skip_check: Whether the field should be checked or not.
    :type skip_check: bool
    :return: A dict of power parameters for all power types, indexed by
        power type name.
    """
    validate(json_power_type_parameters, JSON_POWER_DRIVERS_SCHEMA)
    power_parameters = {
        # Empty type, for the case where nothing is entered in the form yet.
        '': DictCharField(
            [], required=False, skip_check=True),
    }
    if initial_power_params is None:
        initial_power_params = []
    for power_type in json_power_type_parameters:
        fields = []
        has_required_field = False
        for json_field in power_type['fields']:
            field_name = json_field['name']
            if field_name in initial_power_params:
                json_field['default'] = initial_power_params[field_name]
            has_required_field = has_required_field or json_field['required']
            fields.append((
                json_field['name'], make_form_field(json_field)))
        params = DictCharField(
            fields, required=has_required_field, skip_check=skip_check)
        power_parameters[power_type['name']] = params
    return power_parameters


def get_power_type_parameters(initial_power_params=None, skip_check=False):
    return get_power_type_parameters_from_json(
        get_all_power_types_from_clusters(), initial_power_params, skip_check)


def get_power_type_choices():
    """Mutate the power types returned from the cluster into a choices
    structure as used by Django.

    :return: list of (name, description) tuples
    """
    return [
        (power_type['name'], power_type['description'])
        for power_type in get_all_power_types_from_clusters()]


def get_power_types(controllers=None, ignore_errors=False):
    """Return the choice of mechanism to control a node's power.

    :param controllers: Restrict to power types on the supplied
        :class:`RackController`s.
    :param ignore_errors: If comms errors are encountered talking to any
        clusters, ignore and carry on. This means partial data may be
        returned if other clusters are operational.

    :raises: :class:`ClusterUnavailable` if ignore_errors is False and a
        cluster controller is unavailable.

    :return: Dictionary mapping power type to its description.
    """
    types = dict()
    power_types = get_all_power_types_from_clusters(controllers, ignore_errors)
    for power_type in power_types:
        types[power_type['name']] = power_type['description']
    return types


def get_all_power_types_from_clusters(controllers=None, ignore_errors=True):
    """Query every cluster controller and obtain all known power types.

    :return: a list of power types matching the schema
        provisioningserver.drivers.power.JSON_POWER_DRIVERS_SCHEMA
    """
    merged_types = []
    responses = call_clusters(
        cluster.DescribePowerTypes, controllers=controllers,
        ignore_errors=ignore_errors)
    for response in responses:
        power_types = response['power_types']
        for power_type in power_types:
            name = power_type['name']
            fields = power_type.get('fields', [])
            description = power_type['description']
            missing_packages = power_type['missing_packages']
            add_power_type_parameters(
                name, description, fields, missing_packages, merged_types)
    return sorted(merged_types, key=itemgetter("description"))
