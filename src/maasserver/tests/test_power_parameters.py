# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for power parameters."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver.config_forms import DictCharField
from maasserver.power_parameters import POWER_TYPE_PARAMETERS
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.matchers import ContainsAll
from provisioningserver.enum import (
    DEFAULT_POWER_TYPE,
    get_power_types,
    )
from provisioningserver.power.poweraction import PowerAction
from testtools.matchers import (
    AllMatch,
    Equals,
    IsInstance,
    MatchesStructure,
    )


class TestPowerParameterDeclaration(MAASServerTestCase):

    def test_POWER_TYPE_PARAMETERS_is_dict_with_power_type_keys(self):
        power_types = set(get_power_types().keys())
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


class TestPowerActionRendering(MAASServerTestCase):
    """Test that the power templates can be rendered."""

    scenarios = [
        (name, {'power_type': name})
        for name in list(POWER_TYPE_PARAMETERS)
        if name != DEFAULT_POWER_TYPE
    ]

    def make_random_parameters(self, power_change="on"):
        params = {'power_change': power_change}
        param_definition = POWER_TYPE_PARAMETERS[self.power_type]
        for name, field in param_definition.field_dict.items():
            params[name] = factory.make_name(name)
        return params

    def test_render_template(self):
        params = self.make_random_parameters()
        node = factory.make_node(power_type=self.power_type)
        params.update(node.get_effective_power_parameters())
        action = PowerAction(self.power_type)
        script = action.render_template(action.get_template(), **params)
        # The real check is that the rendering went fine.
        self.assertIsInstance(script, bytes)
