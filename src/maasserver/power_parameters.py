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
mapping between the new power type and a list of PowerParameter instances in
`POWER_TYPE_PARAMETERS`.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'POWER_TYPE_PARAMETERS',
    'validate_power_parameters',
    ]

from collections import namedtuple
from operator import attrgetter

from django.core.exceptions import ValidationError
from provisioningserver.enum import POWER_TYPE


PowerParameter = namedtuple(
    'PowerParameter',
    [
        # 'display' will be used in the UI as the title of the field.
        'display',
        # 'name' is the actual name of this parameter as used in the JSON
        # structure (power parameters are stored as JSON dicts).
        'name',
    ])


POWER_TYPE_PARAMETERS = {
    POWER_TYPE.WAKE_ON_LAN:
        [
            PowerParameter(
                display='Address',
                name='power_address',
                ),
        ],
    POWER_TYPE.VIRSH:
        [
            PowerParameter(
                display='Driver',
                name='driver',
                ),
             PowerParameter(
                display='Username',
                name='username',
                ),
             PowerParameter(
                display='Address',
                name='power_address',
                ),
             PowerParameter(
                display='power_id',
                name='power_id',
                ),
         ],
    POWER_TYPE.IPMI:
        [
            PowerParameter(
                display='Address',
                name='power_address',
                ),
            PowerParameter(
                display='User',
                name='power_user',
                ),
            PowerParameter(
                display='Password',
                name='power_pass',
                ),
         ],
    POWER_TYPE.IPMI_LAN:
        [
            PowerParameter(
                display='User',
                name='power_user',
                ),
            PowerParameter(
                display='Password',
                name='power_pass',
                ),
            PowerParameter(
                display='power_id',
                name='power_id',
                ),
        ]
    }


def validate_power_parameters(power_parameters, power_type):
    """Validate that the given power parameters:
    - the given power_parameter argument must be a dictionary.
    - the keys of the given power_parameter argument must be a subset of
      the possible parameters for this power type.
    If one of these assertions is not true, raise a ValidationError.
    """
    if not isinstance(power_parameters, dict):
        raise ValidationError(
            "The given power parameters should be a dictionary.")
    # Fetch the expected power_parameter related to the power_type.  If the
    # power_type is unknown, don't validate power_parameter.  We don't want
    # to block things if one wants to use a custom power_type.
    expected_power_parameters = map(attrgetter(
        'name'), POWER_TYPE_PARAMETERS.get(power_type, []))
    if len(expected_power_parameters) != 0:
        unknown_fields = set(
            power_parameters).difference(expected_power_parameters)
        if len(unknown_fields) != 0:
            raise ValidationError(
                    "These field(s) are invalid for this power type: %s.  "
                    "Allowed fields: %s." % (
                        ', '.join(unknown_fields),
                        ', '.join(expected_power_parameters)))
