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

from maasserver.config_forms import DictCharField
from maasserver.power_parameters import POWER_TYPE_PARAMETERS
from maasserver.testing.testcase import TestCase
from maasserver.utils import map_enum
from maastesting.matchers import ContainsAll
from provisioningserver.enum import POWER_TYPE
from testtools.matchers import (
    AllMatch,
    Equals,
    IsInstance,
    MatchesStructure,
    )


class TestPowerParameterDeclaration(TestCase):

    def test_POWER_TYPE_PARAMETERS_is_dict_with_power_type_keys(self):
        power_types = set(map_enum(POWER_TYPE).values())
        self.assertIsInstance(POWER_TYPE_PARAMETERS, dict)
        self.assertThat(power_types, ContainsAll(POWER_TYPE_PARAMETERS))

    def test_POWER_TYPE_PARAMETERS_values_are_DictCharField(self):
        self.assertThat(
            POWER_TYPE_PARAMETERS.values(),
            AllMatch(IsInstance(DictCharField)))

    def test_POWER_TYPE_PARAMETERS_DictCharField_objects_have_skip_check(self):
        self.assertThat(
            POWER_TYPE_PARAMETERS.values(),
            AllMatch(MatchesStructure(skip_check=Equals(True))))
