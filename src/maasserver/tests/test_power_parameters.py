# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for power parameters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from operator import attrgetter

from django.core.exceptions import ValidationError
from maasserver.power_parameters import (
    POWER_TYPE_PARAMETERS,
    PowerParameter,
    validate_power_parameters,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import TestCase
from maasserver.utils import map_enum
from maastesting.matchers import ContainsAll
from provisioningserver.enum import POWER_TYPE
from testtools.matchers import (
    AllMatch,
    IsInstance,
    )


class TestPowerParameterDeclaration(TestCase):

    def test_POWER_TYPE_PARAMETERS_is_dict_with_power_type_keys(self):
        power_types = set(map_enum(POWER_TYPE).values())
        self.assertIsInstance(POWER_TYPE_PARAMETERS, dict)
        self.assertThat(power_types, ContainsAll(POWER_TYPE_PARAMETERS))

    def test_POWER_TYPE_PARAMETERS_values_are_PowerParameter(self):
        params = sum(POWER_TYPE_PARAMETERS.values(), [])
        self.assertThat(params, AllMatch(IsInstance(PowerParameter)))


class TestPowerParameterHelpers(TestCase):

    def test_validate_power_parameters_requires_dict(self):
        exception = self.assertRaises(
            ValidationError, validate_power_parameters,
            factory.getRandomString(), factory.getRandomString())
        self.assertEqual(
            ["The given power parameters should be a dictionary."],
            exception.messages)

    def test_validate_power_parameters_rejects_unknown_field(self):
        # If power_type is a known power type, the fields in the provided
        # power_parameters dict are checked.
        power_parameters = {"invalid-power-type": factory.getRandomString()}
        power_type = POWER_TYPE.WAKE_ON_LAN
        expected_power_parameters = map(attrgetter(
            'name'), POWER_TYPE_PARAMETERS.get(power_type, []))
        exception = self.assertRaises(
            ValidationError, validate_power_parameters,
            power_parameters, power_type)
        expected_message = (
            "These field(s) are invalid for this power type: "
            "invalid-power-type.  Allowed fields: %s." % ', '.join(
                expected_power_parameters))
        self.assertEqual([expected_message], exception.messages)

    def test_validate_power_parameters_validates_if_unknown_power_type(self):
        # If power_type is not a known power type, no check of the fields in
        # power_parameter is performed.
        power_parameters = {
            factory.getRandomString(): factory.getRandomString()}
        power_type = factory.getRandomString()
        self.assertIsNone(
            validate_power_parameters(power_parameters, power_type))

    def test_validate_power_parameters_validates_with_power_type_info(self):
        power_parameters = {'power_address': factory.getRandomString()}
        power_type = POWER_TYPE.WAKE_ON_LAN
        self.assertIsNone(
            validate_power_parameters(power_parameters, power_type))
