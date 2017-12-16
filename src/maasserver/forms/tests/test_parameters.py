# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for Parameters form."""

__all__ = []

import random

from maasserver.forms.parameters import ParametersForm
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase


class TestParametersForm(MAASServerTestCase):

    def test__validates_parameters_is_dict(self):
        form = ParametersForm(data=[
            factory.make_name() for _ in range(3)])
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {'parameters': ['Must be a dictionary']},
            form.errors)

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

    def test__input_errors_on_unknown_paramater(self):
        script = factory.make_Script()
        bad_param = factory.make_name('bad_param')
        form = ParametersForm(
            data={bad_param: factory.make_name('bad_input')},
            script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'input': ["Unknown parameter '%s' for %s" % (
                    bad_param, script.name)],
            }, form.errors)

    def test__input_runtime(self):
        script = factory.make_Script(
            parameters={'runtime': {'type': 'runtime'}})
        value = random.randint(0, 100)
        form = ParametersForm(
            data={'runtime': value}, script=script, node=factory.make_Node())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEquals(1, len(form.cleaned_data['input']))
        self.assertDictEqual(
            {'runtime': {'type': 'runtime', 'value': value}},
            form.cleaned_data['input'][0])

    def test__input_runtime_gets_default_from_script_timeout(self):
        script = factory.make_Script(
            parameters={'runtime': {'type': 'runtime'}})
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEquals(1, len(form.cleaned_data['input']))
        self.assertDictEqual({'runtime': {
            'type': 'runtime',
            'value': script.timeout.seconds,
            }}, form.cleaned_data['input'][0])

    def test__input_runtime_requires_int(self):
        script = factory.make_Script(
            parameters={'runtime': {'type': 'runtime'}})
        form = ParametersForm(
            data={'runtime': factory.make_name('value')},
            script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'runtime': ["Must be an int"],
            }, form.errors)

    def test__input_runtime_validates_required(self):
        script = factory.make_Script(parameters={'runtime': {
            'type': 'runtime',
            'required': True,
            'default': None,
        }})
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'runtime': ["Field is required"],
            }, form.errors)

    def test__input_runtime_validates_min(self):
        min_runtime = random.randint(1, 100)
        script = factory.make_Script(parameters={'runtime': {
            'type': 'runtime',
            'min': min_runtime,
        }})
        value = random.randint(-min_runtime, min_runtime - 1)
        form = ParametersForm(
            data={'runtime': value}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'runtime': ["Must be greater than %s" % min_runtime],
            }, form.errors)

    def test__input_runtime_validates_max(self):
        max_runtime = random.randint(0, 100)
        script = factory.make_Script(parameters={'runtime': {
            'type': 'runtime',
            'max': max_runtime,
        }})
        value = random.randint(max_runtime + 1, max_runtime + 10)
        form = ParametersForm(
            data={'runtime': value}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'runtime': ["Must be less than %s" % max_runtime],
            }, form.errors)

    def test__input_storage_validates_required(self):
        script = factory.make_Script(parameters={'storage': {
            'type': 'storage',
            'required': True,
            'default': None,
        }})
        form = ParametersForm(data={}, script=script, node=factory.make_Node())
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'storage': ["Field is required"],
            }, form.errors)

    def test__input_storage_defaults_all_with_no_disks(self):
        script = factory.make_Script(parameters={
            'runtime': {'type': 'runtime'},
            'storage': {'type': 'storage'},
        })
        form = ParametersForm(
            data={}, script=script,
            node=factory.make_Node(with_boot_disk=False))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEquals(1, len(form.cleaned_data['input']))
        self.assertDictEqual({
            'runtime': {'type': 'runtime', 'value': script.timeout.seconds},
            'storage': {'type': 'storage', 'value': 'all'},
            }, form.cleaned_data['input'][0])

    def test__input_storage_all(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(parameters={
            'runtime': {'type': 'runtime'},
            'storage': {'type': 'storage'},
        })
        form = ParametersForm(
            data={'storage': 'all'}, script=script, node=node)
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data['input']
        self.assertEquals(node.physicalblockdevice_set.count(), len(input))
        for bd in node.physicalblockdevice_set:
            for i in input:
                if bd.name == i['storage']['value']['name']:
                    break
            self.assertEquals(script.timeout.seconds, i['runtime']['value'])
            self.assertDictEqual({
                'name': bd.name,
                'id_path': bd.id_path,
                'model': bd.model,
                'serial': bd.serial,
                'physical_blockdevice': bd,
                }, i['storage']['value'])

    def test__input_storage_id(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(parameters={
            'runtime': {'type': 'runtime'},
            'storage': {'type': 'storage'},
        })
        bd = random.choice(list(node.physicalblockdevice_set.all()))
        form = ParametersForm(
            data={'storage': random.choice([bd.id, str(bd.id)])},
            script=script, node=node)
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data['input']
        self.assertEquals(1, len(input))
        self.assertEquals(script.timeout.seconds, input[0]['runtime']['value'])
        self.assertDictEqual({
            'name': bd.name,
            'id_path': bd.id_path,
            'model': bd.model,
            'serial': bd.serial,
            'physical_blockdevice': bd,
            }, input[0]['storage']['value'])

    def test__input_storage_id_errors(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(parameters={
            'runtime': {'type': 'runtime'},
            'storage': {'type': 'storage'},
        })
        form = ParametersForm(
            data={'storage': random.randint(1000, 2000)},
            script=script, node=node)
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'storage': ['Physical block id does not exist'],
            }, form.errors)

    def test__input_storage_list(self):
        node = factory.make_Node()
        for _ in range(10):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(parameters={
            'runtime': {'type': 'runtime'},
            'storage': {'type': 'storage'},
        })
        bds = list(node.physicalblockdevice_set.all())
        selected_scripts = {
            bds[0]: '%s:%s' % (bds[0].model, bds[0].serial),
            bds[1]: bds[1].name,
            bds[2]: '/dev/%s' % bds[2].name,
            bds[3]: bds[3].model,
            bds[4]: bds[4].serial,
            bds[5]: random.choice(bds[5].tags),
        }
        form = ParametersForm(
            data={'storage': ','.join(selected_scripts.values())},
            script=script, node=node)
        self.assertTrue(form.is_valid(), form.errors)
        input = form.cleaned_data['input']
        self.assertEquals(len(selected_scripts), len(input))
        for bd in selected_scripts.keys():
            for i in input:
                if bd.name == i['storage']['value']['name']:
                    break
            self.assertEquals(script.timeout.seconds, i['runtime']['value'])
            self.assertDictEqual({
                'name': bd.name,
                'id_path': bd.id_path,
                'model': bd.model,
                'serial': bd.serial,
                'physical_blockdevice': bd,
                }, i['storage']['value'])

    def test__input_storage_name_errors(self):
        node = factory.make_Node()
        for _ in range(3):
            factory.make_PhysicalBlockDevice(node=node)
        script = factory.make_Script(parameters={
            'runtime': {'type': 'runtime'},
            'storage': {'type': 'storage'},
        })
        form = ParametersForm(
            data={'storage': factory.make_name('bad_name')},
            script=script, node=node)
        self.assertFalse(form.is_valid())
        self.assertDictEqual(
            {
                'storage': ['Unknown storage device for %s(%s)' % (
                    node.fqdn, node.system_id)],
            }, form.errors)
