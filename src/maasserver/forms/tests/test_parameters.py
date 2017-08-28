# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Parameters form."""

__all__ = []

import random

from maasserver.forms.parameters import ParametersForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestParametersForm(MAASServerTestCase):

    def test__validates_parameter_is_str(self):
        param = random.randint(0, 1000)
        form = ParametersForm(data={
            param: {
                'type': 'storage',
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["%d: parameter must be a string" % param]
            }, form.errors)

    def test__validates_parameter_field_type_is_str(self):
        param_type = random.randint(0, 1000)
        form = ParametersForm(data={
            'storage': {
                'type': param_type,
                'required': False,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["%d: type must be a string" % param_type]
            }, form.errors)

    def test__validates_parameter_field_min_is_int(self):
        param_min = factory.make_name('min')
        form = ParametersForm(data={
            'runtime': {
                'type': 'runtime',
                'min': param_min,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["%s: min must be an integer" % param_min]
            }, form.errors)

    def test__validates_parameter_field_max_is_int(self):
        param_max = factory.make_name('max')
        form = ParametersForm(data={
            'runtime': {
                'type': 'runtime',
                'max': param_max,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["%s: max must be an integer" % param_max]
            }, form.errors)

    def test__validates_parameter_field_title_is_str(self):
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'title': True,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["True: title must be a string"]
            }, form.errors)

    def test__validates_parameter_field_description_is_str(self):
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'description': True,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["True: description must be a string"]
            }, form.errors)

    def test__validates_parameter_field_argument_format_is_str(self):
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'argument_format': [],
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["[]: argument_format must be a string"]
            }, form.errors)

    def test__validates_parameter_field_argument_format_for_storage_type(self):
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'argument_format': factory.make_name('argument_format'),
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': [
                    "storage: argument_format must contain one of {input}, "
                    "{name}, {path}, {model}, {serial}"]
            }, form.errors)

    def test__validates_parameter_field_argument_format_non_storage_type(self):
        form = ParametersForm(data={
            'runtime': {
                'type': 'runtime',
                'argument_format': factory.make_name('argument_format'),
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["runtime: argument_format must contain {input}"]
            }, form.errors)

    def test__validates_parameter_field_default_is_str(self):
        param_default = random.randint(0, 1000)
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'default': param_default,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["%d: default must be a string" % param_default]
            }, form.errors)

    def test__validates_parameter_field_required_is_boolean(self):
        param_required = factory.make_name('required')
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'required': param_required,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': [
                    "%s: required must be a boolean" % param_required]
            }, form.errors)

    def test__checks_for_supported_parameter_types(self):
        form = ParametersForm(data={
            'storage': {
                'type': 'storage'
            },
            'runtime': {
                'type': 'runtime'
            },
        })
        self.assertTrue(form.is_valid())

    def test__validates_against_unsupported_parameter_types(self):
        unsupported_type = factory.make_name('unsupported')
        form = ParametersForm(data={
            'storage': {
                'type': unsupported_type,
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': [
                    "%s: type must be either storage or runtime"
                    % unsupported_type]
            }, form.errors)

    def test__validates_unsupported_parameter_types_if_not_required(self):
        unsupported_type = factory.make_name('unsupported')
        form = ParametersForm(data={
            'storage': {
                'type': unsupported_type,
                'required': False,
            },
        })
        self.assertTrue(form.is_valid())

    def test__validates_storage_type_has_no_min_or_max(self):
        form = ParametersForm(data={
            'storage': {
                'type': 'storage',
                'min': random.randint(0, 1000),
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["storage type doesn't support min or max"]
            }, form.errors)

    def test__validates_runtime_type_min_greater_than_zero(self):
        form = ParametersForm(data={
            'runtime': {
                'type': 'runtime',
                'min': random.randint(-100, -1),
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["runtime minimum must be greater than zero"]
            }, form.errors)

    def test__validates_min_less_than_max(self):
        form = ParametersForm(data={
            'runtime': {
                'type': 'runtime',
                'min': random.randint(500, 1000),
                'max': random.randint(0, 500),
            },
        })
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'parameters': ["min must be less than max"]
            }, form.errors)
